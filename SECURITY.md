# Security Guide for GOOBITS STT

## 🔐 API Key Management

### Porcupine Wake Word Detection

The wake word detection feature requires a Porcupine access key from Picovoice. **Never commit API keys to version control.**

#### ✅ Secure Methods (Choose One):

**Method 1: Environment Variable (Recommended)**
```bash
export PORCUPINE_ACCESS_KEY="your_key_here"
stt --wake-word
```

**Method 2: .env File**
```bash
# Create .env file (already in .gitignore)
echo 'PORCUPINE_ACCESS_KEY="your_key_here"' > .env
stt --wake-word
```

**Method 3: One-time Usage**
```bash
PORCUPINE_ACCESS_KEY="your_key_here" stt --wake-word
```

#### ❌ Insecure Methods (Avoid):

- Hardcoding keys in source code
- Committing keys in config.json
- Sharing keys in chat/email
- Storing keys in public repositories

### Getting Your Access Key

1. Sign up at [Picovoice Console](https://console.picovoice.ai/)
2. Get your free access key (3 custom models included)
3. Set it using one of the secure methods above

### Key Management Best Practices

- **Rotate keys regularly** - Generate new keys periodically
- **Use environment-specific keys** - Different keys for dev/staging/prod
- **Monitor usage** - Check your Picovoice dashboard for unexpected usage
- **Revoke compromised keys** - Immediately revoke if a key is exposed

### Error Messages

If you see "Porcupine access key is required", the application will guide you to set it securely:

```
Error: Porcupine access key is required. Set it using one of these methods:
1. Environment variable: export PORCUPINE_ACCESS_KEY='your_key_here'
2. Create .env file: echo 'PORCUPINE_ACCESS_KEY="your_key_here"' > .env  
3. Add to config.json (not recommended for production)
Get your free access key at: https://console.picovoice.ai/
```

## 🛡️ Additional Security

### File Permissions

Ensure sensitive files have appropriate permissions:
```bash
chmod 600 .env  # Only owner can read/write
chmod 644 config.json  # Standard config file permissions
```

### Production Deployment

For production deployments:
- Use container orchestration secrets (Kubernetes secrets, Docker secrets)
- Use cloud provider secret management (AWS Secrets Manager, Azure Key Vault)
- Never log or display API keys in application output
- Use least-privilege access principles

### Security Audit

Regularly check for exposed secrets:
```bash
# Check if .env is in git (should show nothing)
git ls-files | grep .env

# Verify .gitignore is working
git status --ignored
```