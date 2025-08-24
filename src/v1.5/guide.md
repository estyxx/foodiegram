# 🚀 Batch Processing Guide - Save 50% on OpenAI Costs!

## 📊 **Cost Comparison**

| Processing Mode | Cost | Speed | Best For |
|---|---|---|---|
| **Batch** | 50% cheaper | Up to 24 hours | Large-scale analysis (20+ recipes) |
| **Concurrent** | Standard rate | ~5-10 minutes | Small batches, immediate results |
| **Auto** | Smart choice | Varies | Let the system decide |

## 🔧 **Installation**

```bash
# Install new dependencies
pip install rich>=13.7.0 aiofiles>=23.0.0

# Or update all requirements
pip install -r requirements.txt
```

## 💡 **Quick Start Examples**

### **Option 1: Auto Mode (Recommended)**
Let the system choose the best processing mode:

```bash
python extract.py --collection-id 17854976980356429 --limit 100 --mode auto
```

### **Option 2: Batch Mode (50% Savings)**
Force batch processing for maximum cost savings:

```bash
python extract.py --collection-id 17854976980356429 --limit 200 --mode batch
```

### **Option 3: Concurrent Mode (Immediate Results)**
Use for small batches or when you need results right away:

```bash
python extract.py --collection-id 17854976980356429 --limit 20 --mode concurrent
```

## 📈 **Cost Analysis Examples**

### **Small Batch (20 recipes)**
- **Concurrent**: ~$0.045 (immediate)
- **Batch**: ~$0.023 (up to 24h)
- **Savings**: $0.022 (48% less)

### **Medium Batch (100 recipes)**
- **Concurrent**: ~$0.225 (30 minutes)
- **Batch**: ~$0.113 (up to 24h)
- **Savings**: $0.112 (50% less)

### **Large Batch (500 recipes)**
- **Concurrent**: ~$1.125 (2.5 hours)
- **Batch**: ~$0.563 (up to 24h)
- **Savings**: $0.562 (50% less) 💰

## 🎯 **When to Use Each Mode**

### **Use Batch Mode When:**
- ✅ Processing 20+ recipes
- ✅ Cost savings are important
- ✅ You can wait up to 24 hours
- ✅ Running overnight or weekly analysis

### **Use Concurrent Mode When:**
- ✅ Processing < 20 recipes
- ✅ Need immediate results
- ✅ Testing new prompts
- ✅ Interactive analysis

### **Use Auto Mode When:**
- ✅ Unsure which to choose
- ✅ Want optimal cost/speed balance
- ✅ Different batch sizes each time

## 📊 **Progress Tracking Features**

The enhanced analyzer includes beautiful progress tracking:

```bash
🔍 Extracting 100 posts from collection 17854976980356429
✅ Successfully extracted 100 posts

💰 Cost Analysis
┏━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Mode       ┃        Cost ┃ Time           ┃ Notes                     ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Batch      │      $0.113 │ < 24 hours     │ 50% discount, async       │
│ Concurrent │      $0.225 │ ~5-10 minutes  │ Standard rate, immediate  │
└────────────┴─────────────┴────────────────┴───────────────────────────┘

💡 Smart Recommendation
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 💡 Recommendation: Use batch mode                                            ┃
┃ Potential savings: $0.11 (50.0%)                                            ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

🚀 Starting analysis in batch mode...
⠋ Processing recipe detection batch: 45/100
```

## 📝 **Extraction History Tracking**

Track your AI improvements over time:

```python
from foodiegram.extraction_history import ExtractionHistoryManager

# Initialize history manager
history = ExtractionHistoryManager()

# View recent runs
recent_runs = history.get_latest_runs(5)
for run in recent_runs:
    print(f"Run {run.run_id}: {run.success_rate:.1f}% success")

# Compare two runs
comparison = history.compare_runs("run_20250815_143022", "run_20250818_091234")
print(f"Success rate improved by {comparison.success_rate_change:.1f}%")
```

## 🏷️ **English Translation Features**

The enhanced analyzer automatically translates Italian recipe terms:

### **Before (Duplicates):**
```json
{
  "vegetables": ["pomodoro", "tomato", "zucchine", "zucchini"],
  "key_ingredients": ["aglio", "garlic", "olio d'oliva", "olive oil"]
}
```

### **After (Clean English):**
```json
{
  "vegetables": ["tomato", "zucchini"],
  "key_ingredients": ["garlic", "olive oil"]
}
```

### **Supported Translations:**
- `pomodoro` → `tomato`
- `zucchine` → `zucchini`
- `aglio` → `garlic`
- `cipolla` → `onion`
- `basilico` → `basil`
- `parmigiano` → `parmesan`
- `olio d'oliva` → `olive oil`
- `sale` → `salt`
- `pepe` → `pepper`

## 🛠️ **Advanced Configuration**

### **Custom Batch Sizes**
```python
from foodiegram.analyzer import EnhancedRecipeAnalyzer

analyzer = EnhancedRecipeAnalyzer(
    openai_api_key="your-key",
    batch_size=1000,  # Custom batch size
    enable_caching=True  # Enable result caching
)
```

### **Custom Prompts**
Create custom prompt files:

```bash
# Create custom prompts
mkdir -p src/foodiegram/prompts
echo "Your custom detection prompt..." > src/foodiegram/prompts/is_recipe.md
echo "Your custom extraction prompt..." > src/foodiegram/prompts/extract_details.md
```

### **Programmatic Usage**
```python
from foodiegram.analyzer import EnhancedRecipeAnalyzer, ProcessingMode

analyzer = EnhancedRecipeAnalyzer(openai_api_key="your-key")

# Get cost estimates
estimate = analyzer.estimate_cost(posts, ProcessingMode.BATCH)
print(f"Estimated cost: ${estimate['estimated_total_cost']:.3f}")

# Get smart recommendations
recommendation = analyzer.get_processing_recommendation(posts)
print(f"Recommended mode: {recommendation['recommended_mode']}")

# Process with progress callback
def progress_callback(description: str, completed: int, total: int):
    print(f"{description}: {completed}/{total}")

recipes = analyzer.analyze_posts_batch_mode(
    posts=posts,
    processing_mode=ProcessingMode.BATCH,
    progress_callback=progress_callback
)
```

## 📊 **Monitoring Batch Jobs**

When using batch mode, you'll see real-time status updates:

```bash
🚀 Starting analysis in batch mode...
📝 Created batch file with 200 requests
📤 Submitted batch job: batch_abc123xyz
⏳ Polling batch abc123xyz for completion...
📊 Batch abc123xyz status: in_progress
📊 Processing recipe detection batch: 150/200
✅ Batch abc123xyz completed in 3.2 minutes
```

## 🎯 **Best Practices**

### **For Cost Optimization:**
1. **Use batch mode for 20+ recipes** - 50% savings
2. **Process overnight** - batch jobs often complete in 1-3 hours
3. **Enable caching** - avoid re-processing same recipes
4. **Batch similar collections** - group related recipe collections

### **For Speed Optimization:**
1. **Use concurrent mode for < 20 recipes**
2. **Enable result caching** - instant results for re-analysis
3. **Use auto mode** - smart choice based on batch size

### **For Quality Optimization:**
1. **Track extraction history** - monitor improvements
2. **Compare runs** - A/B test different prompts
3. **Review confidence scores** - focus on high-confidence extractions
4. **Customize prompts** - tailor to your specific content

## 🚨 **Error Handling**

The system gracefully handles various errors:

### **Batch Failures:**
- Automatic fallback to concurrent processing
- Partial results if batch partially completes
- Detailed error logging and recovery

### **API Rate Limits:**
- Intelligent retry with exponential backoff
- Batch mode uses separate rate limits
- Progress tracking during delays

### **Network Issues:**
- Automatic retry for transient failures
- Partial result preservation
- Resume capability for large batches

## 📈 **Performance Monitoring**

### **View Analysis Summary:**
```bash
📊 Analysis Summary
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                ┃ Value                 ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ Total Posts Analyzed  │ 100                   │
│ Recipes Found         │ 67                    │
│ Non-Recipes          │ 33                    │
│ Success Rate         │ 67.0%                 │
│ Average Confidence   │ 84.2%                 │
└───────────────────────┴───────────────────────┘

🏆 Top Recipes by Confidence
1. Pasta with Garlic and Olive Oil (94.5%)
2. Zucchini Fritters (91.2%)
3. Tomato Basil Salad (89.7%)
```

### **Export History:**
```python
# Export detailed history for analysis
history.export_history(Path("extraction_analysis.json"))
```

## 🎉 **Success Tips**

1. **Start with auto mode** - let the system optimize for you
2. **Monitor your costs** - check estimates before large batches
3. **Use progress tracking** - stay informed during processing
4. **Compare extraction runs** - continuously improve your prompts
5. **Enable caching** - speed up re-analysis and testing

## 🆘 **Troubleshooting**

### **"Batch job failed" Error:**
- Check your OpenAI API key and credits
- Verify network connectivity
- Try concurrent mode as fallback

### **"No recipes found" Result:**
- Review your collection ID
- Check if posts contain actual recipes
- Try lowering confidence threshold

### **Slow Processing:**
- Use batch mode for large collections
- Enable caching for repeated analysis
- Check your internet connection

## 🎯 **Next Steps**

After implementing batch processing, you're ready for:
- **Task 1.2**: English Translation (✅ Already included!)
- **Task 2.2**: History Tracking (✅ Already included!)
- **Task 2.3**: Smart Tag Filtering
- **Task 3.1**: Production Deployment

---

**💡 Pro Tip:** Start with a small batch (20-50 recipes) in auto mode to get familiar with the system, then scale up to larger batches with batch mode for maximum savings!
