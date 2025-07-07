"""
FIXED highlighting.py - Advanced highlighting system for TTS content with speech synchronization
Properly integrates with enhanced_calculations.py and frontend highlighting.ts
"""
import re
import json
import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
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
        """Convert to dictionary for API responses - matches frontend expectations"""
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
        """Convert to dictionary for API responses - matches frontend expectations"""
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
        """Convert to dictionary for API responses - matches frontend expectations"""
        return {
            "text": self.text,
            "segments": [seg.to_dict() for seg in self.segments],
            "words": [word.to_dict() for word in self.words],
            "total_duration": self.total_duration,
            "extraction_method": self.extraction_method,
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            "segment_count": len(self.segments),
            "word_count": len(self.words)
        }

class TextProcessor:
    """Advanced text processing for TTS highlighting"""
    
    @staticmethod
    def normalize_text_for_highlighting(text: str) -> str:
        """Normalize text for consistent highlighting"""
        # Normalize whitespace while preserving structure
        text = re.sub(r'\r\n|\r', '\n', text)  # Normalize line endings
        text = re.sub(r'\n{3,}', '\n\n', text)  # Limit multiple newlines
        text = re.sub(r'[ \t]+', ' ', text)     # Normalize spaces
        text = re.sub(r' +\n', '\n', text)      # Remove trailing spaces
        text = re.sub(r'\n +', '\n', text)      # Remove leading spaces
        
        return text.strip()
    
    @staticmethod
    def create_sentence_segments(text: str) -> List[Dict[str, Any]]:
        """Create sentence-level segments for highlighting"""
        # Enhanced sentence splitting that handles common edge cases
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])\n+(?=[A-Z])|(?<=\.)\s+(?=[A-Z][a-z])'
        
        sentences = re.split(sentence_pattern, text)
        segments = []
        current_pos = 0
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Find actual position in original text
            start_pos = text.find(sentence, current_pos)
            if start_pos == -1:
                # Fallback if exact match fails
                start_pos = current_pos
            
            end_pos = start_pos + len(sentence)
            word_count = len(sentence.split())
            
            segments.append({
                "text": sentence,
                "start_char": start_pos,
                "end_char": end_pos,
                "word_count": word_count,
                "segment_id": f"seg_{i:04d}",
                "type": "sentence"
            })
            
            current_pos = end_pos
        
        return segments
    
    @staticmethod
    def create_paragraph_segments(text: str) -> List[Dict[str, Any]]:
        """Create paragraph-level segments for highlighting"""
        paragraphs = text.split('\n\n')
        segments = []
        current_pos = 0
        
        for i, paragraph in enumerate(paragraphs):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # Find position in original text
            start_pos = text.find(paragraph, current_pos)
            if start_pos == -1:
                start_pos = current_pos
            
            end_pos = start_pos + len(paragraph)
            word_count = len(paragraph.split())
            
            segments.append({
                "text": paragraph,
                "start_char": start_pos,
                "end_char": end_pos,
                "word_count": word_count,
                "segment_id": f"para_{i:04d}",
                "type": "paragraph"
            })
            
            current_pos = end_pos + 2  # Account for \n\n
        
        return segments
    
    @staticmethod
    def extract_words_with_positions(text: str) -> List[Dict[str, Any]]:
        """Extract individual words with their positions"""
        words = []
        word_pattern = r'\b\w+\b'
        
        for match in re.finditer(word_pattern, text):
            words.append({
                "word": match.group(),
                "start_char": match.start(),
                "end_char": match.end()
            })
        
        return words

class SpeechMarkProcessor:
    """Process AWS Polly speech marks for highlighting"""
    
    @staticmethod
    def parse_speech_marks(speech_marks_data: str) -> List[Dict[str, Any]]:
        """Parse Polly speech marks JSON data"""
        try:
            marks = []
            for line in speech_marks_data.strip().split('\n'):
                if line.strip():
                    mark = json.loads(line)
                    marks.append(mark)
            return marks
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing speech marks: {e}")
            return []
    
    @staticmethod
    def align_speech_marks_with_text(
        text: str, 
        speech_marks: List[Dict[str, Any]]
    ) -> List[WordHighlight]:
        """Align speech marks with original text positions"""
        word_highlights = []
        
        # Create word mapping
        text_words = TextProcessor.extract_words_with_positions(text)
        
        # Align speech marks with text positions
        mark_index = 0
        for text_word in text_words:
            if mark_index < len(speech_marks):
                mark = speech_marks[mark_index]
                
                # Check if this word matches the speech mark
                if (mark.get('type') == 'word' and 
                    text_word['word'].lower() == mark.get('value', '').lower()):
                    
                    word_highlights.append(WordHighlight(
                        word=text_word['word'],
                        start_char=text_word['start_char'],
                        end_char=text_word['end_char'],
                        start_time=mark.get('time', 0),
                        end_time=mark.get('time', 0) + 200  # Estimate duration
                    ))
                    mark_index += 1
                else:
                    # Add word without timing if no match
                    word_highlights.append(WordHighlight(
                        word=text_word['word'],
                        start_char=text_word['start_char'],
                        end_char=text_word['end_char'],
                        start_time=0,
                        end_time=200
                    ))
            else:
                # No more speech marks, estimate timing
                estimated_time = len(word_highlights) * 250  # 250ms per word average
                word_highlights.append(WordHighlight(
                    word=text_word['word'],
                    start_char=text_word['start_char'],
                    end_char=text_word['end_char'],
                    start_time=estimated_time,
                    end_time=estimated_time + 250
                ))
        
        return word_highlights

class HighlightGenerator:
    """Main class for generating highlighting maps"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.speech_mark_processor = SpeechMarkProcessor()
    
    def create_highlight_map(
        self,
        text: str,
        speech_marks_data: Optional[str] = None,
        extraction_method: str = "unknown",
        segment_type: str = "sentence"
    ) -> HighlightMap:
        """Create a complete highlighting map for TTS content"""
        
        # Normalize text
        normalized_text = self.text_processor.normalize_text_for_highlighting(text)
        
        # Create segments based on type
        if segment_type == "paragraph":
            segments_data = self.text_processor.create_paragraph_segments(normalized_text)
        else:
            segments_data = self.text_processor.create_sentence_segments(normalized_text)
        
        # Process speech marks if available
        word_highlights = []
        if speech_marks_data:
            speech_marks = self.speech_mark_processor.parse_speech_marks(speech_marks_data)
            word_highlights = self.speech_mark_processor.align_speech_marks_with_text(
                normalized_text, speech_marks
            )
        
        # Create segments with timing
        segments = []
        current_time = 0.0
        
        for seg_data in segments_data:
            # Estimate timing based on word count (average 200ms per word)
            estimated_duration = seg_data['word_count'] * 200
            
            segment = HighlightSegment(
                text=seg_data['text'],
                start_char=seg_data['start_char'],
                end_char=seg_data['end_char'],
                start_time=current_time,
                end_time=current_time + estimated_duration,
                word_count=seg_data['word_count'],
                segment_id=seg_data['segment_id']
            )
            
            segments.append(segment)
            current_time += estimated_duration + 100  # 100ms pause between segments
        
        # Calculate total duration
        total_duration = segments[-1].end_time if segments else 0.0
        
        return HighlightMap(
            text=normalized_text,
            segments=segments,
            words=word_highlights,
            total_duration=total_duration,
            extraction_method=extraction_method,
            created_at=datetime.now(timezone.utc)
        )
    
    def create_reading_chunks(
        self, 
        text: str, 
        max_chunk_size: int = 3000,
        overlap_sentences: int = 1
    ) -> List[Dict[str, Any]]:
        """Create optimized reading chunks for long texts"""
        
        # First, split into sentences
        sentences = self.text_processor.create_sentence_segments(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        chunk_id = 0
        
        for i, sentence in enumerate(sentences):
            sentence_length = len(sentence['text'])
            
            # Check if adding this sentence would exceed max size
            if current_length + sentence_length > max_chunk_size and current_chunk:
                # Create chunk from current sentences
                chunk_text = ' '.join([s['text'] for s in current_chunk])
                chunk_start = current_chunk[0]['start_char']
                chunk_end = current_chunk[-1]['end_char']
                
                chunks.append({
                    "chunk_id": f"chunk_{chunk_id:03d}",
                    "text": chunk_text,
                    "start_char": chunk_start,
                    "end_char": chunk_end,
                    "sentence_count": len(current_chunk),
                    "word_count": sum(s['word_count'] for s in current_chunk),
                    "estimated_duration": sum(s['word_count'] for s in current_chunk) * 200
                })
                
                # Start new chunk with overlap
                if overlap_sentences > 0 and len(current_chunk) > overlap_sentences:
                    current_chunk = current_chunk[-overlap_sentences:]
                    current_length = sum(len(s['text']) for s in current_chunk)
                else:
                    current_chunk = []
                    current_length = 0
                
                chunk_id += 1
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add final chunk if any sentences remain
        if current_chunk:
            chunk_text = ' '.join([s['text'] for s in current_chunk])
            chunk_start = current_chunk[0]['start_char']
            chunk_end = current_chunk[-1]['end_char']
            
            chunks.append({
                "chunk_id": f"chunk_{chunk_id:03d}",
                "text": chunk_text,
                "start_char": chunk_start,
                "end_char": chunk_end,
                "sentence_count": len(current_chunk),
                "word_count": sum(s['word_count'] for s in current_chunk),
                "estimated_duration": sum(s['word_count'] for s in current_chunk) * 200
            })
        
        return chunks
    
    def validate_highlight_map(self, highlight_map: HighlightMap) -> Dict[str, Any]:
        """Validate highlighting map for consistency"""
        issues = []
        warnings = []
        
        # Check segment overlap
        for i in range(len(highlight_map.segments) - 1):
            current = highlight_map.segments[i]
            next_seg = highlight_map.segments[i + 1]
            
            if current.end_char > next_seg.start_char:
                issues.append(f"Segment overlap: {current.segment_id} and {next_seg.segment_id}")
            
            if current.end_time > next_seg.start_time:
                warnings.append(f"Timing overlap: {current.segment_id} and {next_seg.segment_id}")
        
        # Check for gaps in coverage
        total_text_length = len(highlight_map.text)
        covered_chars = sum(seg.end_char - seg.start_char for seg in highlight_map.segments)
        coverage_ratio = covered_chars / total_text_length if total_text_length > 0 else 0
        
        if coverage_ratio < 0.9:
            warnings.append(f"Low text coverage: {coverage_ratio:.2%}")
        
        # Check timing consistency
        if highlight_map.segments:
            actual_duration = highlight_map.segments[-1].end_time
            if abs(actual_duration - highlight_map.total_duration) > 1000:  # 1 second tolerance
                warnings.append("Total duration mismatch")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "coverage_ratio": coverage_ratio,
            "segment_count": len(highlight_map.segments),
            "word_count": len(highlight_map.words)
        }

# Utility functions for highlighting that enhanced_calculations.py imports
def create_basic_highlight_map(text: str, extraction_method: str = "unknown") -> HighlightMap:
    """Create a basic highlighting map without speech marks"""
    generator = HighlightGenerator()
    return generator.create_highlight_map(text, extraction_method=extraction_method)

def create_highlight_with_speech_marks(
    text: str, 
    speech_marks_data: str,
    extraction_method: str = "polly"
) -> HighlightMap:
    """Create highlighting map with Polly speech marks"""
    generator = HighlightGenerator()
    return generator.create_highlight_map(
        text, 
        speech_marks_data=speech_marks_data,
        extraction_method=extraction_method
    )

def optimize_text_for_highlighting(text: str) -> str:
    """Optimize text for better highlighting results"""
    processor = TextProcessor()
    return processor.normalize_text_for_highlighting(text)

# Additional utility functions for enhanced_calculations.py integration
def create_enhanced_highlight_map_from_backend_data(
    text: str,
    backend_segments: List[Dict[str, Any]],
    backend_words: List[Dict[str, Any]],
    extraction_method: str = "backend"
) -> HighlightMap:
    """Create highlight map from backend segment and word data"""
    
    # Convert backend segments to HighlightSegment objects
    segments = []
    for seg_data in backend_segments:
        segments.append(HighlightSegment(
            text=seg_data.get('text', ''),
            start_char=seg_data.get('start_char', 0),
            end_char=seg_data.get('end_char', 0),
            start_time=seg_data.get('start_time', 0),
            end_time=seg_data.get('end_time', 0),
            word_count=seg_data.get('word_count', 0),
            segment_id=seg_data.get('segment_id', ''),
            confidence=seg_data.get('confidence', 1.0)
        ))
    
    # Convert backend words to WordHighlight objects
    words = []
    for word_data in backend_words:
        words.append(WordHighlight(
            word=word_data.get('word', ''),
            start_char=word_data.get('start_char', 0),
            end_char=word_data.get('end_char', 0),
            start_time=word_data.get('start_time', 0),
            end_time=word_data.get('end_time', 0)
        ))
    
    # Calculate total duration
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
    """Merge multiple highlight maps into one"""
    if not highlight_maps:
        return create_basic_highlight_map("")
    
    if len(highlight_maps) == 1:
        return highlight_maps[0]
    
    # Combine all text
    combined_text = ""
    combined_segments = []
    combined_words = []
    total_duration = 0
    char_offset = 0
    time_offset = 0
    
    for highlight_map in highlight_maps:
        # Adjust character positions for combined text
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
        
        # Adjust word positions for combined text
        for word in highlight_map.words:
            adjusted_word = WordHighlight(
                word=word.word,
                start_char=word.start_char + char_offset,
                end_char=word.end_char + char_offset,
                start_time=word.start_time + time_offset,
                end_time=word.end_time + time_offset
            )
            combined_words.append(adjusted_word)
        
        # Update offsets for next map
        combined_text += highlight_map.text + " "
        char_offset = len(combined_text)
        time_offset += highlight_map.total_duration + 500  # 500ms pause between maps
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
    """Validate that highlighting map is compatible with given text"""
    issues = []
    
    # Check text length compatibility
    if len(highlight_map.text) != len(text):
        issues.append(f"Text length mismatch: highlight_map has {len(highlight_map.text)}, provided text has {len(text)}")
    
    # Check segment positions
    for segment in highlight_map.segments:
        if segment.end_char > len(text):
            issues.append(f"Segment {segment.segment_id} end position {segment.end_char} exceeds text length {len(text)}")
        
        if segment.start_char < 0:
            issues.append(f"Segment {segment.segment_id} has negative start position {segment.start_char}")
    
    # Check word positions
    for i, word in enumerate(highlight_map.words):
        if word.end_char > len(text):
            issues.append(f"Word {i} end position {word.end_char} exceeds text length {len(text)}")
        
        if word.start_char < 0:
            issues.append(f"Word {i} has negative start position {word.start_char}")
    
    return {
        "compatible": len(issues) == 0,
        "issues": issues,
        "text_length_match": len(highlight_map.text) == len(text),
        "segment_positions_valid": all(0 <= seg.start_char <= seg.end_char <= len(text) for seg in highlight_map.segments),
        "word_positions_valid": all(0 <= word.start_char <= word.end_char <= len(text) for word in highlight_map.words)
    }

# Export classes and functions for enhanced_calculations.py
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