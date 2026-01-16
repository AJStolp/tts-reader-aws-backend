# Upgrade to t3.medium - Step by Step

## Check Current Instance Type

1. **Go to AWS Console**: https://console.aws.amazon.com/ec2
2. **Select your region** (top right - make sure it's where you deployed)
3. **Click "Instances" in left sidebar**
4. **Find your TTS Reader backend instance**
5. **Look at the "Instance Type" column**

### What you might see:
- **t2.micro** (Free tier) - 1 vCPU, 1GB RAM - TOO SMALL
- **t2.small** - 1 vCPU, 2GB RAM - TOO SMALL
- **t3.small** - 2 vCPUs, 2GB RAM - MIGHT WORK
- **t3.medium** - 2 vCPUs, 4GB RAM - **TARGET** ✅

---

## Upgrade to t3.medium (If Needed)

### Method 1: Using AWS Console (Easiest)

1. **Select your instance** (checkbox on the left)
2. **Click "Instance state" → "Stop instance"**
   - Wait 1-2 minutes for it to fully stop
   - Status will change to "Stopped"

3. **With instance still selected, click "Actions" → "Instance settings" → "Change instance type"**
4. **Select "t3.medium" from dropdown**
5. **Click "Apply"**
6. **Click "Instance state" → "Start instance"**
   - Wait 1-2 minutes for it to start
   - Status will change to "Running"

**Done! Your instance is now t3.medium**

### Method 2: Using AWS CLI (If you have it configured)

```bash
# Get your instance ID
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,State.Name,Tags[?Key==`Name`].Value|[0]]' --output table

# Stop instance (replace i-xxxxx with your instance ID)
aws ec2 stop-instances --instance-ids i-xxxxx

# Wait for it to stop
aws ec2 wait instance-stopped --instance-ids i-xxxxx

# Change instance type
aws ec2 modify-instance-attribute --instance-id i-xxxxx --instance-type t3.medium

# Start instance
aws ec2 start-instances --instance-ids i-xxxxx

# Wait for it to start
aws ec2 wait instance-running --instance-ids i-xxxxx
```

---

## After Upgrade: Test Your Backend

### 1. Find your backend URL
```bash
# In AWS Console, select your instance and look for:
# "Public IPv4 DNS" or "Public IPv4 address"
# Example: ec2-54-123-45-67.compute-1.amazonaws.com
```

### 2. Test the health endpoint
```bash
curl http://YOUR-EC2-ADDRESS:5000/api/health
# Should return: {"status": "healthy"}
```

### 3. Update locust.conf for AWS testing
Edit `locust.conf`:
```ini
host = http://YOUR-EC2-ADDRESS:5000
```

### 4. Run load test against AWS
```bash
# Start with smoke test
./run_load_tests.sh smoke --aws

# Then realistic load
./run_load_tests.sh load --aws
```

---

## Cost Impact

**Before (assuming t2.micro)**:
- Free tier or ~$8/month

**After (t3.medium)**:
- ~$30/month ($0.0416/hour)

**Can I save money?**
- Yes! Stop the instance when not testing
- Or use t3.medium only during load testing, then switch back

---

## Important Notes

⚠️ **Downtime**: Your backend will be offline for 2-5 minutes during the upgrade
⚠️ **IP Address**: Public IP might change (use Elastic IP if you need static IP)
⚠️ **Security Groups**: Should remain the same (port 5000 must be open)
⚠️ **Data**: All data/code on the instance is preserved

---

## Troubleshooting

### Backend won't start after upgrade?
```bash
# SSH into instance
ssh -i your-key.pem ec2-user@YOUR-EC2-ADDRESS

# Check backend status
ps aux | grep uvicorn

# Restart if needed
cd /path/to/tts-reader-aws-backend
source tts_reader_env/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5000 &
```

### Can't connect to instance?
- Check Security Group allows inbound on port 5000
- Check instance is "Running" in console
- Check you're using the right IP/DNS

---

## Next Steps After Upgrade

1. ✅ Verify instance is running
2. ✅ Test health endpoint
3. ✅ Update locust.conf with AWS URL
4. ✅ Run smoke test (5 users)
5. ✅ Run realistic load test (50 users)
6. ✅ Run stress test (200-500 users)
7. ✅ Analyze results
8. ✅ Launch! 🚀

---

## Quick Reference

```bash
# Test backend health
curl http://YOUR-EC2-IP:5000/api/health

# Update locust config
nano locust.conf
# Change: host = http://YOUR-EC2-IP:5000

# Run tests
./quick_load_test.sh  # Interactive menu
./run_load_tests.sh smoke --aws
./run_load_tests.sh load --aws
./run_load_tests.sh stress --aws
```
