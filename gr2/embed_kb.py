#!/usr/bin/env python3
# gr2/embed_kb.py
# Knowledge Base Embedding and Management Script

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gr2.config import BTC_OPTIONS_KB

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KBManager:
    """Manage knowledge base documents and embeddings."""
    
    def __init__(self, kb_dir: str = "kb_docs", kb_file: str = "knowledge_base.json"):
        self.kb_dir = Path(kb_dir)
        self.kb_file = self.kb_dir / kb_file
        self.kb_dir.mkdir(exist_ok=True)
        self._load_kb()
    
    def _load_kb(self):
        """Load existing knowledge base."""
        if self.kb_file.exists():
            with open(self.kb_file, 'r') as f:
                self.knowledge_base = json.load(f)
        else:
            self.knowledge_base = BTC_OPTIONS_KB.copy()
            self._save_kb()
    
    def _save_kb(self):
        """Save knowledge base to file."""
        with open(self.kb_file, 'w') as f:
            json.dump(self.knowledge_base, f, indent=2)
        logger.info(f"Knowledge base saved to {self.kb_file}")
    
    def add_document(self, title: str, content: str, topic: str = "general"):
        """
        Add a new document to the knowledge base.
        
        Args:
            title: Document title
            content: Document content
            topic: Topic category (basics, greeks, strategy, etc.)
        """
        new_doc = {
            "title": title,
            "content": content,
            "topic": topic
        }
        
        # Check for duplicates
        for doc in self.knowledge_base:
            if doc["title"] == title:
                logger.warning(f"Document with title '{title}' already exists. Skipping.")
                return False
        
        self.knowledge_base.append(new_doc)
        self._save_kb()
        logger.info(f"Added document: {title}")
        return True
    
    def add_from_markdown(self, file_path: str, topic: str = "general"):
        """
        Add document from markdown file.
        
        Args:
            file_path: Path to markdown file
            topic: Topic category
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return False
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Extract title from first line or filename
            lines = content.strip().split('\n')
            title = lines[0].strip('#').strip() if lines[0].startswith('#') else file_path.stem
            
            # Remove title from content if it was a header
            if lines[0].startswith('#'):
                content = '\n'.join(lines[1:]).strip()
            
            return self.add_document(title, content, topic)
            
        except Exception as e:
            logger.error(f"Error adding from markdown {file_path}: {e}")
            return False
    
    def list_documents(self, topic: str = None):
        """List all documents, optionally filtered by topic."""
        if topic:
            docs = [doc for doc in self.knowledge_base if doc.get("topic") == topic]
        else:
            docs = self.knowledge_base
        
        print(f"\nKnowledge Base Documents ({len(docs)} total):")
        print("-" * 50)
        
        for i, doc in enumerate(docs, 1):
            print(f"{i}. {doc['title']} [{doc.get('topic', 'general')}]")
            print(f"   {doc['content'][:100]}...")
            print()
    
    def get_topics(self):
        """Get list of all topics in the knowledge base."""
        topics = set(doc.get("topic", "general") for doc in self.knowledge_base)
        return sorted(list(topics))
    
    def update_config(self):
        """Update the config.py file with current knowledge base."""
        try:
            config_path = Path(__file__).parent / "config.py"
            
            with open(config_path, 'r') as f:
                config_content = f.read()
            
            # Find the BTC_OPTIONS_KB section and replace it
            start_marker = "BTC_OPTIONS_KB = ["
            end_marker = "]"
            
            start_idx = config_content.find(start_marker)
            if start_idx == -1:
                logger.error("Could not find BTC_OPTIONS_KB in config.py")
                return False
            
            # Find the end of the list
            brace_count = 0
            end_idx = start_idx + len(start_marker)
            for i, char in enumerate(config_content[start_idx + len(start_marker):]):
                if char == '[':
                    brace_count += 1
                elif char == ']':
                    if brace_count == 0:
                        end_idx = start_idx + len(start_marker) + i + 1
                        break
                    brace_count -= 1
            
            # Create new KB content
            kb_content = "[\n"
            for doc in self.knowledge_base:
                kb_content += f"    {{\n"
                kb_content += f'        "title": "{doc["title"]}",\n'
                kb_content += f'        "content": "{doc["content"].replace('"', '\\"')}",\n'
                kb_content += f'        "topic": "{doc.get("topic", "general")}"\n'
                kb_content += f"    }},\n"
            kb_content += "]"
            
            # Replace the content
            new_config = config_content[:start_idx] + start_marker + kb_content + config_content[end_idx:]
            
            with open(config_path, 'w') as f:
                f.write(new_config)
            
            logger.info("Updated config.py with new knowledge base")
            return True
            
        except Exception as e:
            logger.error(f"Error updating config.py: {e}")
            return False

def main():
    """Main CLI interface."""
    kb_manager = KBManager()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python embed_kb.py list [topic]     - List documents")
        print("  python embed_kb.py add <file> [topic] - Add markdown file")
        print("  python embed_kb.py topics           - List topics")
        print("  python embed_kb.py update-config    - Update config.py")
        return
    
    command = sys.argv[1]
    
    if command == "list":
        topic = sys.argv[2] if len(sys.argv) > 2 else None
        kb_manager.list_documents(topic)
    
    elif command == "add":
        if len(sys.argv) < 3:
            print("Error: Please specify a file to add")
            return
        
        file_path = sys.argv[2]
        topic = sys.argv[3] if len(sys.argv) > 3 else "general"
        
        if kb_manager.add_from_markdown(file_path, topic):
            print(f"Successfully added {file_path}")
        else:
            print(f"Failed to add {file_path}")
    
    elif command == "topics":
        topics = kb_manager.get_topics()
        print("Available topics:")
        for topic in topics:
            count = len([doc for doc in kb_manager.knowledge_base if doc.get("topic") == topic])
            print(f"  {topic}: {count} documents")
    
    elif command == "update-config":
        if kb_manager.update_config():
            print("Successfully updated config.py")
        else:
            print("Failed to update config.py")
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main() 