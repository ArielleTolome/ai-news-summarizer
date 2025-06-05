"""
Simple Dagger module for AI News Summarizer
"""

import dagger
from dagger import dag, function, object_type


@object_type
class AiNewsSummarizer:
    """AI News Summarizer Module"""
    
    @function
    def hello(self, name: str = "World") -> str:
        """Say hello"""
        return f"Hello {name} from AI News Summarizer!"
    
    @function
    async def test(self) -> str:
        """Test the news summarizer"""
        container = (
            dag.container()
            .from_("python:3.11-slim")
            .with_exec(["echo", "AI News Summarizer is working!"])
        )
        
        return await container.stdout()