import re
import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class HighlightSegment:
    """Represents a highlighted text segment for TTS"""
    text: str
    start_char: int
    end_char: int
    start_time: float  # milliseconds
    end_time: float    # milliseconds
    word_count: int
    segment_id: str
    confidence: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "word_count": self.word_count,
            "segment_id": self.segment_id,
            "confidence": self.confidence,
            "duration": self.end_time - self.start_time
        }

@dataclass
class WordHighlight:
    """Individual word highlighting for precise TTS sync"""
    word: str
    start_char: int
    end_char: int
    start_time: float
    end_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "start_time": self.start_time,
            "end_time": self.end_time
        }

@dataclass
class HighlightMap:
    """Complete highlighting map for TTS content"""
    text: str
    segments: List[HighlightSegment]
    words: List[WordHighlight]
    total_duration: float
    extraction_method: str
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "segments": [seg.to_dict() for seg in self.segments],
            "words": [word.to_dict() for word in self.words],
            "total_duration": self.total_duration,
            "extraction_method": self.extraction_method,
            "created_at": self.created_at.isoformat(),
            "segment_count": len(self.segments),
            "word_count": len(self.words)
        }

class TextProcessor:
    """Advanced text processing for TTS highlighting"""
    
    @staticmethod
    def normalize_text_for_highlighting(text: str) -> str:
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r' +\n', '\n', text)
        text = re.sub(r'\n +', '\n', text)
        return text.strip()

class SpeechMarkProcessor:
    """Process AWS Polly speech marks for highlighting"""
    
    @staticmethod
    def process_speech_marks(speech_marks: List[Dict[str, Any]], input_text: str) -> Dict[str, Any]:
        """Process Polly speech marks with robust text alignment"""
        sentences = []
        words = []
        current_sentence = ""
        sentence_start = 0
        sentence_time = 0
        clean_text = TextProcessor.normalize_text_for_highlighting(input_text)
        char_index = 0

        for mark in sorted(speech_marks, key=lambda x: x['time']):
            clean_value = mark['value'].strip()
            if not clean_value:
                continue

            # Try finding from char_index, fallback to entire text
            start_pos = clean_text.find(clean_value, char_index)
            if start_pos == -1:
                start_pos = clean_text.find(clean_value)  # Search entire text
                if start_pos == -1:
                    logger.warning(f"Could not find '{clean_value}' in text at index {char_index}")
                    continue
            end_pos = start_pos + len(clean_value)
            char_index = max(char_index, start_pos)  # Update index but don't overshoot

            if mark['type'] == 'sentence':
                if current_sentence:
                    clean_start_prev = clean_text.find(current_sentence, sentence_start)
                    if clean_start_prev == -1:
                        clean_start_prev = sentence_start
                    clean_end_prev = clean_start_prev + len(current_sentence)
                    sentences.append({
                        "text": current_sentence,
                        "start_char": clean_start_prev,
                        "end_char": clean_end_prev,
                        "start_time": sentence_time,
                        "end_time": mark['time'],
                        "word_count": len(current_sentence.split())
                    })
                current_sentence = clean_value
                sentence_start = start_pos
                sentence_time = mark['time']
            elif mark['type'] == 'word':
                words.append({
                    "word": clean_value,
                    "start_char": start_pos,
                    "end_char": end_pos,
                    "start_time": mark['time'],
                    "end_time": mark.get('end_time', mark['time'] + 150)
                })

        # Finalize last sentence
        if current_sentence:
            clean_start = clean_text.find(current_sentence, sentence_start)
            if clean_start == -1:
                clean_start = sentence_start
            clean_end = clean_start + len(current_sentence)
            sentences.append({
                "text": current_sentence,
                "start_char": clean_start,
                "end_char": clean_end,
                "start_time": sentence_time,
                "end_time": speech_marks[-1]['time'] if speech_marks else 0,
                "word_count": len(current_sentence.split())
            })

        # Validate positions
        for seg in sentences:
            if seg['end_char'] > len(clean_text) or seg['start_char'] < 0:
                logger.warning(f"Invalid sentence position: {seg['text']} at {seg['start_char']}-{seg['end_char']}")
                sentences.remove(seg)
        for word in words:
            if word['end_char'] > len(clean_text) or word['start_char'] < 0:
                logger.warning(f"Invalid word position: {word['word']} at {word['start_char']}-{word['end_char']}")
                words.remove(word)

        logger.info(f"[SpeechMarkProcessor] Processed {len(sentences)} sentences and {len(words)} words")
        logger.debug(f"[SpeechMarkProcessor] Clean text length: {len(clean_text)}")
        
        return {
            "sentences": sentences,
            "words": words,
            "total_duration": speech_marks[-1]['time'] if speech_marks else 0
        }

class HighlightGenerator:
    """Generate comprehensive highlighting maps"""
    
    @staticmethod
    def generate_highlight_map(text: str, speech_marks: Optional[List[Dict[str, Any]]] = None, 
                             extraction_method: str = "generic") -> HighlightMap:
        processor = TextProcessor()
        normalized_text = processor.normalize_text_for_highlighting(text)
        if speech_marks:
            processed_marks = SpeechMarkProcessor.process_speech_marks(speech_marks, normalized_text)
            segments = processed_marks['sentences']
            words = processed_marks['words']
            total_duration = processed_marks['total_duration']
        else:
            # Fallback to basic segmentation if no speech marks
            segments = processor.create_sentence_segments(normalized_text) or processor.create_paragraph_segments(normalized_text)
            words_data = processor.extract_words_with_positions(normalized_text)
            total_duration = 0
            segments, words = processor.estimate_timing(segments, words_data, total_duration)
        
        highlight_segments = [
            HighlightSegment(
                text=seg['text'],
                start_char=seg['start_char'],
                end_char=seg['end_char'],
                start_time=seg.get('start_time', 0),
                end_time=seg.get('end_time', 0),
                word_count=seg['word_count'],
                segment_id=seg.get('segment_id', f"seg_{i:04d}"),
                confidence=1.0
            ) for i, seg in enumerate(segments)
        ]
        
        highlight_words = [
            WordHighlight(
                word=word['word'],
                start_char=word['start_char'],
                end_char=word['end_char'],
                start_time=word.get('start_time', 0),
                end_time=word.get('end_time', 0)
            ) for word in words
        ]
        
        return HighlightMap(
            text=normalized_text,
            segments=highlight_segments,
            words=highlight_words,
            total_duration=total_duration or max([s.end_time for s in highlight_segments] or [0]),
            extraction_method=extraction_method,
            created_at=datetime.now(timezone.utc)
        )

def create_basic_highlight_map(text: str, extraction_method: str = "generic") -> HighlightMap:
    return HighlightGenerator.generate_highlight_map(text, extraction_method=extraction_method)

def create_highlight_with_speech_marks(text: str, speech_marks: List[Dict[str, Any]]) -> HighlightMap:
    return HighlightGenerator.generate_highlight_map(text, speech_marks, extraction_method="speech_marks")

def optimize_text_for_highlighting(text: str) -> str:
    processor = TextProcessor()
    return processor.normalize_text_for_highlighting(text)

def create_enhanced_highlight_map_from_backend_data(
    text: str,
    backend_segments: List[Dict[str, Any]],
    backend_words: List[Dict[str, Any]],
    extraction_method: str = "backend"
) -> HighlightMap:
    segments = [
        HighlightSegment(
            text=seg_data.get('text', ''),
            start_char=seg_data.get('start_char', 0),
            end_char=seg_data.get('end_char', 0),
            start_time=seg_data.get('start_time', 0),
            end_time=seg_data.get('end_time', 0),
            word_count=seg_data.get('word_count', 0),
            segment_id=seg_data.get('segment_id', ''),
            confidence=seg_data.get('confidence', 1.0)
        ) for seg_data in backend_segments
    ]
    words = [
        WordHighlight(
            word=word_data.get('word', ''),
            start_char=word_data.get('start_char', 0),
            end_char=word_data.get('end_char', 0),
            start_time=word_data.get('start_time', 0),
            end_time=word_data.get('end_time', 0)
        ) for word_data in backend_words
    ]
    total_duration = max([seg.end_time for seg in segments]) if segments else 0
    return HighlightMap(
        text=text,
        segments=segments,
        words=words,
        total_duration=total_duration,
        extraction_method=extraction_method,
        created_at=datetime.now(timezone.utc)
    )

def merge_highlight_maps(highlight_maps: List[HighlightMap]) -> HighlightMap:
    if not highlight_maps:
        return create_basic_highlight_map("")
    if len(highlight_maps) == 1:
        return highlight_maps[0]
    combined_text = ""
    combined_segments = []
    combined_words = []
    total_duration = 0
    char_offset = 0
    time_offset = 0
    for highlight_map in highlight_maps:
        for segment in highlight_map.segments:
            adjusted_segment = HighlightSegment(
                text=segment.text,
                start_char=segment.start_char + char_offset,
                end_char=segment.end_char + char_offset,
                start_time=segment.start_time + time_offset,
                end_time=segment.end_time + time_offset,
                word_count=segment.word_count,
                segment_id=f"merged_{segment.segment_id}",
                confidence=segment.confidence
            )
            combined_segments.append(adjusted_segment)
        for word in highlight_map.words:
            adjusted_word = WordHighlight(
                word=word.word,
                start_char=word.start_char + char_offset,
                end_char=word.end_char + char_offset,
                start_time=word.start_time + time_offset,
                end_time=word.end_time + time_offset
            )
            combined_words.append(adjusted_word)
        combined_text += highlight_map.text + " "
        char_offset = len(combined_text)
        time_offset += highlight_map.total_duration + 500
        total_duration = time_offset
    return HighlightMap(
        text=combined_text.strip(),
        segments=combined_segments,
        words=combined_words,
        total_duration=total_duration,
        extraction_method="merged",
        created_at=datetime.now(timezone.utc)
    )

def validate_highlighting_compatibility(highlight_map: HighlightMap, text: str) -> Dict[str, Any]:
    issues = []
    clean_text = TextProcessor.normalize_text_for_highlighting(text)
    if len(highlight_map.text) != len(clean_text):
        issues.append(f"Text length mismatch: highlight_map has {len(highlight_map.text)}, provided text has {len(clean_text)}")
    for segment in highlight_map.segments:
        if segment.end_char > len(clean_text):
            issues.append(f"Segment {segment.segment_id} end position {segment.end_char} exceeds clean text length {len(clean_text)}")
        if segment.start_char < 0:
            issues.append(f"Segment {segment.segment_id} has negative start position {segment.start_char}")
        segment_text = clean_text[segment.start_char:segment.end_char]
        if segment_text != segment.text:
            issues.append(f"Segment {segment.segment_id} text mismatch: expected '{segment.text}', got '{segment_text}'")
    for i, word in enumerate(highlight_map.words):
        if word.end_char > len(clean_text):
            issues.append(f"Word {i} end position {word.end_char} exceeds clean text length {len(clean_text)}")
        if word.start_char < 0:
            issues.append(f"Word {i} has negative start position {word.start_char}")
        word_text = clean_text[word.start_char:word.end_char]
        if word_text != word.word:
            issues.append(f"Word {i} text mismatch: expected '{word.word}', got '{word_text}'")
    if issues:
        logger.warning(f"[SpeechMarkProcessor] Validation issues: {issues}")
    return {
        "compatible": len(issues) == 0,
        "issues": issues,
        "text_length_match": len(highlight_map.text) == len(clean_text),
        "segment_positions_valid": all(0 <= seg.start_char <= seg.end_char <= len(clean_text) for seg in highlight_map.segments),
        "word_positions_valid": all(0 <= word.start_char <= word.end_char <= len(clean_text) for word in highlight_map.words)
    }

__all__ = [
    'HighlightSegment',
    'WordHighlight', 
    'HighlightMap',
    'TextProcessor',
    'SpeechMarkProcessor',
    'HighlightGenerator',
    'create_basic_highlight_map',
    'create_highlight_with_speech_marks',
    'optimize_text_for_highlighting',
    'create_enhanced_highlight_map_from_backend_data',
    'merge_highlight_maps',
    'validate_highlighting_compatibility'
]