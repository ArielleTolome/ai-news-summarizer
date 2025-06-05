# AI News Summarizer Pipeline

An automated, modular, and scalable AI-powered news summarization system using Dagger. This pipeline automatically collects, summarizes, and publishes content from configurable sources, making it easy to stay updated on any niche topic.

## 🚀 Features

- **Multi-Source Scraping**: Support for both web scraping (CSS/XPath) and RSS/Atom feeds
- **AI-Powered Summarization**: Uses OpenAI GPT or Anthropic Claude for intelligent content summarization
- **Smart Deduplication**: Avoids processing duplicate content across sources
- **Multi-Platform Publishing**: Publish to Markdown files, Twitter threads, and GitHub Pages
- **Trend Detection**: Automatically identifies emerging topics and patterns
- **Dagger Integration**: Containerized pipeline with parallel processing and caching
- **Highly Configurable**: YAML-based configuration for easy customization
- **Production Ready**: Includes error handling, logging, and monitoring

## 📋 Prerequisites

- Python 3.11+
- Dagger CLI installed ([installation guide](https://docs.dagger.io/install))
- API Keys:
  - Anthropic Claude API key (or OpenAI API key)
  - GitHub token (for GitHub publishing)
  - Twitter API keys (optional, for Twitter publishing)

## 🛠️ Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-news-summarizer.git
cd ai-news-summarizer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
# Or for OpenAI:
# export OPENAI_API_KEY="your-openai-api-key"

# For GitHub publishing:
export GITHUB_TOKEN="your-github-token"

# For Twitter publishing (optional):
export TWITTER_API_KEYS='{"consumer_key":"...","consumer_secret":"...","access_token":"...","access_token_secret":"..."}'
```

4. Configure your sources in `config/config.yaml`:
```yaml
niche: "AI"  # Change to your desired niche
sources:
  rss_feeds:
    - url: "https://example.com/feed"
      name: "Example Feed"
```

## 🚀 Quick Start

### Run Once
```bash
python -m src.pipeline.news_pipeline
```

### Run with Preview (no publishing)
```bash
python -m src.pipeline.news_pipeline --preview
```

### Run on Schedule
```bash
python -m src.pipeline.news_pipeline --scheduled
```

### Using Docker
```bash
docker build -t ai-news-summarizer .
docker run -v $(pwd)/output:/app/output ai-news-summarizer
```

### Using Dagger
```bash
dagger run python -m src.pipeline.news_pipeline
```

## 📁 Project Structure

```
ai-news-summarizer/
├── src/
│   ├── scrapers/
│   │   ├── web_scraper.py      # Web scraping with CSS/XPath
│   │   └── rss_parser.py       # RSS/Atom feed parsing
│   ├── summarizers/
│   │   └── gpt_summarizer.py   # AI-powered summarization
│   ├── publishers/
│   │   ├── markdown_publisher.py
│   │   ├── twitter_publisher.py
│   │   └── github_publisher.py
│   └── pipeline/
│       └── news_pipeline.py    # Main pipeline orchestration
├── config/
│   └── config.yaml            # Configuration file
├── templates/
│   └── newsletter_template.md # Jinja2 template
├── output/                    # Generated newsletters
├── cache/                     # Article deduplication cache
└── metrics/                   # Pipeline metrics
```

## ⚙️ Configuration

### Basic Configuration

Edit `config/config.yaml` to customize:

```yaml
niche: "AI"  # Your topic of interest

sources:
  rss_feeds:
    - url: "https://techcrunch.com/feed/"
      name: "TechCrunch"
      max_articles: 10
      
  web_scraping:
    - url: "https://example.com/news"
      selectors:
        articles: "article h2 a"  # CSS selector
        title: "//h1[@class='title']"  # XPath
        content: ".article-body"

summarization:
  provider: "anthropic"  # or "openai"
  model: "claude-3-opus-20240229"
  max_articles_per_run: 20

publishing:
  markdown:
    enabled: true
    output_dir: "./output"
```

### Advanced Features

#### Custom Selectors
```yaml
web_scraping:
  - url: "https://news.site.com"
    selectors:
      articles: "//article//a[@class='headline']"  # XPath
      title: "h1.article-title"  # CSS
      content: ".story-body"
      author: "span.byline"
      date: "time[datetime]"
```

#### Multi-Language Support
```yaml
languages: ["en", "es", "fr"]  # Coming soon
```

#### Email Newsletter
```yaml
email:
  enabled: true
  provider: "sendgrid"
  api_key_env: "SENDGRID_API_KEY"
  subscriber_list_id: "your-list-id"
```

## 📊 Output Examples

### Markdown Newsletter
The pipeline generates beautiful markdown newsletters with:
- Executive summary
- Top stories with key insights
- Trend analysis
- Full article summaries
- Metadata and statistics

### Twitter Thread
Automatically creates engaging Twitter threads with:
- Newsletter highlights
- Top 3 stories
- Trending topics
- Link to full newsletter

### GitHub Pages
Publishes to GitHub repository with:
- Organized directory structure
- Auto-generated index
- Archive of all newsletters
- Individual article pages

## 🔧 Customization

### Adding a New Source Type

1. Create a new scraper in `src/scrapers/`:
```python
class CustomScraper:
    async def scrape(self, config):
        # Your scraping logic
        return articles
```

2. Update the pipeline to use your scraper.

### Custom Summarization Prompts

Modify prompts in `src/summarizers/gpt_summarizer.py`:
```python
prompt = f"""
Your custom prompt here...
Article: {article_content}
"""
```

### New Publisher

1. Create a new publisher in `src/publishers/`:
```python
class CustomPublisher:
    async def publish(self, content):
        # Your publishing logic
```

2. Add configuration in `config.yaml`.

## 🧪 Testing

Run tests:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=src tests/
```

## 🐛 Troubleshooting

### Common Issues

1. **Rate Limiting**: Adjust `rate_limit_delay` in config
2. **API Errors**: Check your API keys and quotas
3. **Scraping Failures**: Verify selectors match current site structure
4. **Memory Issues**: Reduce `max_articles_per_run`

### Debug Mode

Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Monitoring

Pipeline metrics are saved to `metrics/pipeline_metrics.json`:
```json
{
  "start_time": "2024-06-04T09:00:00",
  "end_time": "2024-06-04T09:15:30",
  "articles_scraped": 45,
  "articles_summarized": 20,
  "articles_published": 20,
  "duration_seconds": 930
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- Built with [Dagger](https://dagger.io/) for containerized pipelines
- Powered by [Anthropic Claude](https://www.anthropic.com/) and [OpenAI](https://openai.com/)
- Inspired by the need for curated, AI-powered news digests

## 🚧 Roadmap

- [ ] Web dashboard for configuration
- [ ] Slack/Discord integration
- [ ] Custom ML models for relevance scoring
- [ ] Multi-language support
- [ ] Podcast generation
- [ ] Mobile app notifications

---

Built with ❤️ for the AI community