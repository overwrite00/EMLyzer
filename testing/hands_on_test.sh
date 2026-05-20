#!/bin/bash
# Hands-on testing of EMLyzer with real email samples

EMAIL_DIR="D:\Documenti\Email per test analisi"
OUTPUT_DIR="D:\GitHub\EMLyzer\testing"
API_BASE="http://localhost:8000/api"

echo "================================================================================"
echo "EMLYZER HANDS-ON TESTING - Practical Analysis of Real Email Samples"
echo "================================================================================"

# Select 15 diverse samples (by file size)
echo -e "\n📧 Selecting 15 diverse email samples..."

# Get sorted files
declare -a FILES
mapfile -t FILES < <(find "$EMAIL_DIR" -name "*.eml" -type f -printf '%s %p\n' | sort -n | awk '{print $2}')

TOTAL=${#FILES[@]}
echo "✓ Found $TOTAL email files"

# Select diverse samples (small, medium, large terciles)
TERCILE=$((TOTAL / 3))
SMALL_END=$TERCILE
MEDIUM_END=$((TERCILE * 2))

declare -a SAMPLES

# Small files (tercile 1)
for ((i=0; i<SMALL_END; i+=SMALL_END/5)); do
    SAMPLES+=("${FILES[$i]}")
done

# Medium files (tercile 2)
for ((i=SMALL_END; i<MEDIUM_END; i+=(MEDIUM_END-SMALL_END)/5)); do
    SAMPLES+=("${FILES[$i]}")
done

# Large files (tercile 3)
for ((i=MEDIUM_END; i<TOTAL; i+=(TOTAL-MEDIUM_END)/5)); do
    SAMPLES+=("${FILES[$i]}")
done

# Trim to 15
SAMPLES=("${SAMPLES[@]:0:15}")
SAMPLE_COUNT=${#SAMPLES[@]}

echo "✓ Selected $SAMPLE_COUNT samples"
echo ""

# Create JSON results structure
cat > "$OUTPUT_DIR/hands_on_test_results.json" << 'EOF'
{
  "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')",
  "total_samples": 0,
  "analyses": [],
  "statistics": {},
  "issues": []
}
EOF

# Analyze each sample
SUCCESS_COUNT=0
declare -A RISK_COUNTS

for ((idx=0; idx<SAMPLE_COUNT; idx++)); do
    FILE="${SAMPLES[$idx]}"
    FILENAME=$(basename "$FILE")
    FILE_SIZE=$(du -k "$FILE" | cut -f1)

    echo "[$((idx+1))/$SAMPLE_COUNT] Analyzing $FILENAME ($FILE_SIZE KB)..."

    # Upload
    UPLOAD_RESP=$(curl -s -X POST -F "file=@$FILE" "$API_BASE/upload/")
    JOB_ID=$(echo "$UPLOAD_RESP" | grep -o '"job_id":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$JOB_ID" ]; then
        echo "  ❌ Upload failed"
        continue
    fi

    echo "  ✓ Uploaded (job_id: ${JOB_ID:0:8}...)"

    # Analyze
    sleep 1
    ANALYSIS_RESP=$(curl -s -X POST "$API_BASE/analysis/$JOB_ID")
    RISK_SCORE=$(echo "$ANALYSIS_RESP" | grep -o '"risk_score":[0-9.]*' | cut -d':' -f2)
    RISK_LABEL=$(echo "$ANALYSIS_RESP" | grep -o '"risk_label":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$RISK_SCORE" ]; then
        echo "  ❌ Analysis failed"
        continue
    fi

    echo "  ✓ Analysis complete: $RISK_LABEL ($RISK_SCORE/100)"

    # Count indicators
    HEADER_IND=$(echo "$ANALYSIS_RESP" | grep -o '"header_indicators"' | wc -l)
    BODY_IND=$(echo "$ANALYSIS_RESP" | grep -o '"body_indicators"' | wc -l)

    echo "  Indicators found (approx)"

    SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    RISK_COUNTS[$RISK_LABEL]=$((${RISK_COUNTS[$RISK_LABEL]:-0} + 1))

done

echo ""
echo "================================================================================"
echo "SUMMARY"
echo "================================================================================"
echo ""
echo "Analyzed: $SUCCESS_COUNT/$SAMPLE_COUNT emails"
echo ""
echo "Risk Distribution:"
for LABEL in "${!RISK_COUNTS[@]}"; do
    COUNT=${RISK_COUNTS[$LABEL]}
    PCT=$((100 * COUNT / SUCCESS_COUNT))
    echo "  ${LABEL^^}: $COUNT ($PCT%)"
done

echo ""
echo "Results will be saved to: $OUTPUT_DIR/hands_on_test_results.json"
