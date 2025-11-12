"""
Session ID Generator Module

Generates human-readable session IDs using Christian/Bible-themed vocabulary.
Format: {adjective}-{noun}-{3-digit-number}
Example: faithful-shepherd-427
"""

import random
import os
import logging
from typing import Optional, Set, Callable

logger = logging.getLogger(__name__)


class SessionIDGenerator:
    """
    Generate unique, human-readable session IDs with Christian/Bible-themed words.
    """
    
    def __init__(
        self,
        adjectives_file: str = None,
        nouns_file: str = None,
        blacklist_file: str = None,
        max_attempts: int = 10
    ):
        """
        Initialize the session ID generator.
        
        Args:
            adjectives_file: Path to adjectives word list file
            nouns_file: Path to nouns word list file
            blacklist_file: Path to blacklist word list file
            max_attempts: Maximum attempts to generate unique ID (default: 10)
        """
        self.max_attempts = max_attempts
        
        # Default paths relative to this file
        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config'
        )
        
        self.adjectives_file = adjectives_file or os.path.join(config_dir, 'adjectives.txt')
        self.nouns_file = nouns_file or os.path.join(config_dir, 'nouns.txt')
        self.blacklist_file = blacklist_file or os.path.join(config_dir, 'blacklist.txt')
        
        # Load word lists at initialization (Lambda container reuse)
        self.adjectives: list[str] = []
        self.nouns: list[str] = []
        self.blacklist: Set[str] = set()
        
        self._load_word_lists()
        
        logger.info(
            f"SessionIDGenerator initialized with {len(self.adjectives)} adjectives, "
            f"{len(self.nouns)} nouns, {len(self.blacklist)} blacklisted words"
        )
    
    def _load_word_lists(self) -> None:
        """Load word lists from files."""
        try:
            # Load adjectives
            with open(self.adjectives_file, 'r') as f:
                self.adjectives = [
                    line.strip().lower() 
                    for line in f 
                    if line.strip() and not line.strip().startswith('#')
                ]
            
            # Load nouns
            with open(self.nouns_file, 'r') as f:
                self.nouns = [
                    line.strip().lower() 
                    for line in f 
                    if line.strip() and not line.strip().startswith('#')
                ]
            
            # Load blacklist
            with open(self.blacklist_file, 'r') as f:
                self.blacklist = {
                    line.strip().lower() 
                    for line in f 
                    if line.strip() and not line.strip().startswith('#')
                }
            
            # Validate word lists
            if len(self.adjectives) < 100:
                logger.warning(
                    f"Adjectives list has only {len(self.adjectives)} words, "
                    "recommend at least 100"
                )
            
            if len(self.nouns) < 100:
                logger.warning(
                    f"Nouns list has only {len(self.nouns)} words, "
                    "recommend at least 100"
                )
        
        except FileNotFoundError as e:
            logger.error(f"Word list file not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading word lists: {e}")
            raise
    
    def _is_blacklisted(self, adjective: str, noun: str) -> bool:
        """
        Check if either word is in the blacklist.
        
        Args:
            adjective: The adjective to check
            noun: The noun to check
        
        Returns:
            True if either word is blacklisted
        """
        return adjective.lower() in self.blacklist or noun.lower() in self.blacklist
    
    def _generate_candidate(self) -> str:
        """
        Generate a candidate session ID.
        
        Returns:
            Session ID in format {adjective}-{noun}-{number}
        """
        adjective = random.choice(self.adjectives)
        noun = random.choice(self.nouns)
        number = random.randint(100, 999)
        
        return f"{adjective}-{noun}-{number}"
    
    def generate(
        self,
        uniqueness_check: Optional[Callable[[str], bool]] = None
    ) -> str:
        """
        Generate a unique session ID.
        
        Args:
            uniqueness_check: Optional callable that returns True if session ID is unique.
                            If None, only blacklist filtering is performed.
        
        Returns:
            Unique session ID in format {adjective}-{noun}-{number}
        
        Raises:
            RuntimeError: If unable to generate unique ID after max_attempts
        """
        for attempt in range(self.max_attempts):
            # Generate candidate
            session_id = self._generate_candidate()
            adjective, noun, _ = session_id.split('-')
            
            # Check blacklist
            if self._is_blacklisted(adjective, noun):
                logger.debug(
                    f"Attempt {attempt + 1}: Generated ID '{session_id}' "
                    "contains blacklisted word, retrying"
                )
                continue
            
            # Check uniqueness if checker provided
            if uniqueness_check is not None:
                if not uniqueness_check(session_id):
                    logger.debug(
                        f"Attempt {attempt + 1}: Generated ID '{session_id}' "
                        "already exists, retrying"
                    )
                    continue
            
            # Success
            logger.info(
                f"Generated session ID '{session_id}' on attempt {attempt + 1}"
            )
            return session_id
        
        # Failed to generate unique ID
        error_msg = (
            f"Failed to generate unique session ID after {self.max_attempts} attempts"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    @staticmethod
    def validate_format(session_id: str) -> bool:
        """
        Validate session ID format.
        
        Args:
            session_id: Session ID to validate
        
        Returns:
            True if format is valid (adjective-noun-number pattern)
        """
        if not session_id:
            return False
        
        parts = session_id.split('-')
        if len(parts) != 3:
            return False
        
        adjective, noun, number = parts
        
        # Check adjective and noun contain only letters and digits (alphanumeric)
        # This allows words like "adjective54" from test files
        if not adjective or not noun:
            return False
        
        # Must start with a letter and be alphanumeric
        if not adjective[0].isalpha() or not noun[0].isalpha():
            return False
        
        if not adjective.replace('_', '').isalnum() or not noun.replace('_', '').isalnum():
            return False
        
        # Check number is 3 digits
        if not number.isdigit() or len(number) != 3:
            return False
        
        # Check number is in valid range
        try:
            num_value = int(number)
            if num_value < 100 or num_value > 999:
                return False
        except ValueError:
            return False
        
        return True
