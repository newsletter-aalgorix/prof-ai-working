# PowerShell script to encode your API keys to Base64 for secrets.yaml
# Run this script and copy the output to 3-secrets.yaml

Write-Host "`n==================================" -ForegroundColor Cyan
Write-Host "  API Key Base64 Encoder" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Function to encode to base64
function Encode-Base64 {
    param([string]$text)
    [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
}

# Prompt for API keys
Write-Host "`nEnter your API keys (they will be encoded to Base64):`n" -ForegroundColor Yellow

$openaiKey = Read-Host "OpenAI API Key (sk-...)"
$sarvamKey = Read-Host "Sarvam API Key"
$groqKey = Read-Host "Groq API Key (gsk_...)"
$elevenlabsKey = Read-Host "ElevenLabs API Key"

Write-Host "`nChromaDB Cloud (optional - press Enter to skip):" -ForegroundColor Yellow
$chromaKey = Read-Host "ChromaDB API Key (or press Enter)"
$chromaTenant = Read-Host "ChromaDB Tenant (or press Enter)"
$chromaDatabase = Read-Host "ChromaDB Database (or press Enter)"

# Encode
Write-Host "`n==================================" -ForegroundColor Green
Write-Host "  Encoded Values (Base64)" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green

Write-Host "`nCopy these values to k8s/3-secrets.yaml:`n" -ForegroundColor Cyan

if ($openaiKey) {
    $encoded = Encode-Base64 $openaiKey
    Write-Host "OPENAI_API_KEY: `"$encoded`""
}

if ($sarvamKey) {
    $encoded = Encode-Base64 $sarvamKey
    Write-Host "SARVAM_API_KEY: `"$encoded`""
}

if ($groqKey) {
    $encoded = Encode-Base64 $groqKey
    Write-Host "GROQ_API_KEY: `"$encoded`""
}

if ($elevenlabsKey) {
    $encoded = Encode-Base64 $elevenlabsKey
    Write-Host "ELEVENLABS_API_KEY: `"$encoded`""
}

if ($chromaKey) {
    $encoded = Encode-Base64 $chromaKey
    Write-Host "CHROMA_CLOUD_API_KEY: `"$encoded`""
}

if ($chromaTenant) {
    $encoded = Encode-Base64 $chromaTenant
    Write-Host "CHROMA_CLOUD_TENANT: `"$encoded`""
}

if ($chromaDatabase) {
    $encoded = Encode-Base64 $chromaDatabase
    Write-Host "CHROMA_CLOUD_DATABASE: `"$encoded`""
}

Write-Host "`n==================================" -ForegroundColor Green
Write-Host "Done! Update 3-secrets.yaml with these values." -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green

pause
