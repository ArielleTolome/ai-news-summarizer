import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import asyncio

from github import Github, GithubException
import git

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitHubPublisher:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
        
        if self.enabled:
            # Initialize GitHub client
            token = os.getenv(config.get('token_env', 'GITHUB_TOKEN'))
            if not token:
                raise ValueError("GitHub token not found in environment")
            
            self.github = Github(token)
            self.repo_name = config['repo']
            self.branch = config.get('branch', 'main')
            self.local_repo_path = Path(config.get('local_repo_path', './github_repo'))
            
            # Setup repository
            self._setup_repository()
    
    def _setup_repository(self):
        """Setup local repository for publishing."""
        try:
            # Get repository
            self.repo = self.github.get_repo(self.repo_name)
            
            # Clone or pull repository
            if self.local_repo_path.exists() and (self.local_repo_path / '.git').exists():
                # Pull latest changes
                self.git_repo = git.Repo(self.local_repo_path)
                origin = self.git_repo.remote('origin')
                origin.pull(self.branch)
                logger.info(f"Pulled latest changes from {self.repo_name}")
            else:
                # Clone repository
                self.local_repo_path.mkdir(parents=True, exist_ok=True)
                self.git_repo = git.Repo.clone_from(
                    self.repo.clone_url.replace('https://', f'https://x-access-token:{os.getenv(self.config.get("token_env", "GITHUB_TOKEN"))}@'),
                    self.local_repo_path,
                    branch=self.branch
                )
                logger.info(f"Cloned repository {self.repo_name}")
                
        except Exception as e:
            logger.error(f"Error setting up repository: {e}")
            raise
    
    def _prepare_content_directory(self) -> Path:
        """Prepare directory structure for content."""
        # Create directory structure
        content_dir = self.local_repo_path / 'content'
        newsletters_dir = content_dir / 'newsletters'
        articles_dir = content_dir / 'articles'
        assets_dir = content_dir / 'assets'
        
        for directory in [content_dir, newsletters_dir, articles_dir, assets_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        return content_dir
    
    def _generate_index_page(self, content_dir: Path) -> str:
        """Generate or update the main index page."""
        index_content = f"""# AI News Digest

*Automatically updated by AI News Summarizer*

Last updated: {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}

## Latest Newsletter

[Read the latest newsletter](./content/newsletters/latest.md)

## Archives

### Newsletters
Browse all newsletters in the [newsletters directory](./content/newsletters/).

### Individual Articles
Browse individual article summaries in the [articles directory](./content/articles/).

## About

This repository contains AI-generated summaries of news articles, automatically updated daily.

---

*Powered by [AI News Summarizer](https://github.com/yourusername/ai-news-summarizer)*
"""
        
        index_path = self.local_repo_path / 'README.md'
        index_path.write_text(index_content, encoding='utf-8')
        
        return str(index_path)
    
    def _copy_content_files(self, source_files: List[str], content_dir: Path) -> List[str]:
        """Copy content files to repository."""
        copied_files = []
        
        for source_file in source_files:
            source_path = Path(source_file)
            
            if not source_path.exists():
                logger.warning(f"Source file not found: {source_file}")
                continue
            
            # Determine destination
            if 'articles' in source_path.parts:
                dest_dir = content_dir / 'articles'
            else:
                dest_dir = content_dir / 'newsletters'
            
            dest_path = dest_dir / source_path.name
            
            # Copy file
            dest_path.write_text(source_path.read_text(encoding='utf-8'), encoding='utf-8')
            copied_files.append(str(dest_path.relative_to(self.local_repo_path)))
            
            # Update latest symlink for newsletters
            if 'newsletters' in str(dest_path) and source_path.name != 'latest.md':
                latest_path = dest_dir / 'latest.md'
                latest_path.write_text(source_path.read_text(encoding='utf-8'), encoding='utf-8')
                copied_files.append(str(latest_path.relative_to(self.local_repo_path)))
        
        return copied_files
    
    async def publish_to_github(self, content_files: List[str], 
                               commit_message: Optional[str] = None) -> bool:
        """Publish content files to GitHub repository."""
        if not self.enabled:
            logger.info("GitHub publishing is disabled")
            return False
        
        try:
            # Pull latest changes
            origin = self.git_repo.remote('origin')
            origin.pull(self.branch)
            
            # Prepare content directory
            content_dir = self._prepare_content_directory()
            
            # Copy content files
            copied_files = self._copy_content_files(content_files, content_dir)
            
            if not copied_files:
                logger.warning("No files to publish")
                return False
            
            # Generate/update index
            index_file = self._generate_index_page(content_dir)
            copied_files.append('README.md')
            
            # Stage files
            self.git_repo.index.add(copied_files)
            
            # Check if there are changes
            if not self.git_repo.index.diff("HEAD"):
                logger.info("No changes to commit")
                return True
            
            # Commit
            if not commit_message:
                commit_message = f"Update news digest - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            self.git_repo.index.commit(commit_message)
            
            # Push
            origin.push(self.branch)
            
            logger.info(f"Successfully published {len(copied_files)} files to GitHub")
            
            # Get GitHub Pages URL if enabled
            if self._is_github_pages_enabled():
                pages_url = self._get_github_pages_url()
                logger.info(f"Content available at: {pages_url}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error publishing to GitHub: {e}")
            # Try to reset repository state
            try:
                self.git_repo.git.reset('--hard', 'HEAD')
            except:
                pass
            return False
    
    def _is_github_pages_enabled(self) -> bool:
        """Check if GitHub Pages is enabled for the repository."""
        try:
            # Check if gh-pages branch exists or if Pages is configured
            branches = [b.name for b in self.repo.get_branches()]
            return 'gh-pages' in branches or self.branch in ['main', 'master']
        except:
            return False
    
    def _get_github_pages_url(self) -> str:
        """Get the GitHub Pages URL for the repository."""
        owner, repo_name = self.repo_name.split('/')
        
        # Check for custom domain
        try:
            cname_content = self.repo.get_contents('CNAME').decoded_content.decode('utf-8').strip()
            return f"https://{cname_content}"
        except:
            # Default GitHub Pages URL
            if repo_name == f"{owner}.github.io":
                return f"https://{owner}.github.io"
            else:
                return f"https://{owner}.github.io/{repo_name}"
    
    async def setup_github_pages(self) -> bool:
        """Setup GitHub Pages for the repository."""
        if not self.enabled:
            return False
        
        try:
            # Enable Pages via API (requires appropriate permissions)
            # This is a simplified version - full implementation would use GitHub API
            logger.info("GitHub Pages should be enabled manually in repository settings")
            logger.info(f"Go to: https://github.com/{self.repo_name}/settings/pages")
            logger.info(f"Select source branch: {self.branch}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up GitHub Pages: {e}")
            return False
    
    async def create_issue_for_errors(self, errors: List[str], 
                                    title: Optional[str] = None) -> Optional[str]:
        """Create a GitHub issue for any errors encountered."""
        if not self.enabled or not errors:
            return None
        
        try:
            if not title:
                title = f"Newsletter Generation Errors - {datetime.now().strftime('%Y-%m-%d')}"
            
            body = "The following errors were encountered during newsletter generation:\n\n"
            for error in errors:
                body += f"- {error}\n"
            
            body += "\n*This issue was automatically created by the AI News Summarizer*"
            
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=['automated', 'error-report']
            )
            
            logger.info(f"Created issue: {issue.html_url}")
            return issue.html_url
            
        except Exception as e:
            logger.error(f"Error creating issue: {e}")
            return None


async def main():
    """Example usage."""
    config = {
        'enabled': True,
        'token_env': 'GITHUB_TOKEN',
        'repo': 'username/ai-news-digest',
        'branch': 'main',
        'local_repo_path': './github_repo'
    }
    
    publisher = GitHubPublisher(config)
    
    # Example files to publish
    content_files = [
        './output/2024-06-04-ai-digest.md',
        './output/articles/2024-06-04-ai-breakthrough.md'
    ]
    
    # Publish to GitHub
    success = await publisher.publish_to_github(
        content_files,
        commit_message="Add AI news digest for June 4, 2024"
    )
    
    if success:
        print("Successfully published to GitHub!")
    else:
        print("Failed to publish to GitHub")


if __name__ == "__main__":
    asyncio.run(main())