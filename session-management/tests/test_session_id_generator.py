"""
Unit tests for Session ID Generator.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch

from shared.utils.session_id_generator import SessionIDGenerator


class TestSessionIDGenerator:
    """Test cases for SessionIDGenerator."""
    
    @pytest.fixture
    def temp_word_files(self):
        """Create temporary word list files for testing."""
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        # Create adjectives file
        adjectives_file = os.path.join(temp_dir, 'adjectives.txt')
        with open(adjectives_file, 'w') as f:
            adjectives = ['faithful', 'blessed', 'gracious', 'righteous', 'holy']
            # Add more to reach 100+
            for i in range(100):
                f.write(f'adjective{i}\n')
            for adj in adjectives:
                f.write(f'{adj}\n')
        
        # Create nouns file
        nouns_file = os.path.join(temp_dir, 'nouns.txt')
        with open(nouns_file, 'w') as f:
            nouns = ['shepherd', 'covenant', 'temple', 'prophet', 'apostle']
            # Add more to reach 100+
            for i in range(100):
                f.write(f'noun{i}\n')
            for noun in nouns:
                f.write(f'{noun}\n')
        
        # Create blacklist file
        blacklist_file = os.path.join(temp_dir, 'blacklist.txt')
        with open(blacklist_file, 'w') as f:
            f.write('damn\n')
            f.write('hell\n')
            f.write('bloody\n')
        
        yield {
            'adjectives': adjectives_file,
            'nouns': nouns_file,
            'blacklist': blacklist_file
        }
        
        # Cleanup
        for file in [adjectives_file, nouns_file, blacklist_file]:
            if os.path.exists(file):
                os.remove(file)
        os.rmdir(temp_dir)
    
    def test_initialization_with_default_paths(self):
        """Test generator initializes with default word list paths."""
        generator = SessionIDGenerator()
        
        assert len(generator.adjectives) > 0
        assert len(generator.nouns) > 0
        assert isinstance(generator.blacklist, set)
    
    def test_initialization_with_custom_paths(self, temp_word_files):
        """Test generator initializes with custom word list paths."""
        generator = SessionIDGenerator(
            adjectives_file=temp_word_files['adjectives'],
            nouns_file=temp_word_files['nouns'],
            blacklist_file=temp_word_files['blacklist']
        )
        
        assert len(generator.adjectives) >= 100
        assert len(generator.nouns) >= 100
        assert len(generator.blacklist) == 3
    
    def test_generate_format_validation(self, temp_word_files):
        """Test generated session ID matches adjective-noun-number pattern."""
        generator = SessionIDGenerator(
            adjectives_file=temp_word_files['adjectives'],
            nouns_file=temp_word_files['nouns'],
            blacklist_file=temp_word_files['blacklist']
        )
        
        session_id = generator.generate()
        
        # Validate format
        assert SessionIDGenerator.validate_format(session_id)
        
        # Check parts
        parts = session_id.split('-')
        assert len(parts) == 3
        
        adjective, noun, number = parts
        # Words can be alphanumeric (test files have adjective0, noun0, etc.)
        assert adjective[0].isalpha()  # Must start with letter
        assert noun[0].isalpha()  # Must start with letter
        assert number.isdigit()
        assert len(number) == 3
        assert 100 <= int(number) <= 999
    
    def test_blacklist_filtering(self, temp_word_files):
        """Test that blacklisted words are filtered out."""
        # Create files with only blacklisted words
        temp_dir = os.path.dirname(temp_word_files['adjectives'])
        
        blacklisted_adj_file = os.path.join(temp_dir, 'blacklisted_adj.txt')
        with open(blacklisted_adj_file, 'w') as f:
            f.write('damn\n')
            f.write('hell\n')
        
        good_nouns_file = os.path.join(temp_dir, 'good_nouns.txt')
        with open(good_nouns_file, 'w') as f:
            for i in range(100):
                f.write(f'noun{i}\n')
        
        generator = SessionIDGenerator(
            adjectives_file=blacklisted_adj_file,
            nouns_file=good_nouns_file,
            blacklist_file=temp_word_files['blacklist'],
            max_attempts=5
        )
        
        # Should fail because all adjectives are blacklisted
        with pytest.raises(RuntimeError, match='Failed to generate unique session ID'):
            generator.generate()
        
        # Cleanup
        os.remove(blacklisted_adj_file)
        os.remove(good_nouns_file)
    
    def test_uniqueness_collision_handling(self, temp_word_files):
        """Test uniqueness collision handling with retry logic."""
        generator = SessionIDGenerator(
            adjectives_file=temp_word_files['adjectives'],
            nouns_file=temp_word_files['nouns'],
            blacklist_file=temp_word_files['blacklist'],
            max_attempts=5
        )
        
        # Mock uniqueness check to fail first 2 times, then succeed
        call_count = 0
        def mock_uniqueness_check(session_id):
            nonlocal call_count
            call_count += 1
            return call_count > 2  # Fail first 2, succeed on 3rd
        
        session_id = generator.generate(uniqueness_check=mock_uniqueness_check)
        
        assert SessionIDGenerator.validate_format(session_id)
        assert call_count == 3  # Should have been called 3 times
    
    def test_max_retry_limit_behavior(self, temp_word_files):
        """Test that max retry limit is enforced."""
        generator = SessionIDGenerator(
            adjectives_file=temp_word_files['adjectives'],
            nouns_file=temp_word_files['nouns'],
            blacklist_file=temp_word_files['blacklist'],
            max_attempts=3
        )
        
        # Mock uniqueness check to always fail
        def always_fails(session_id):
            return False  # Always indicate collision
        
        with pytest.raises(RuntimeError, match='Failed to generate unique session ID after 3 attempts'):
            generator.generate(uniqueness_check=always_fails)
    
    def test_validate_format_valid_ids(self):
        """Test format validation accepts valid session IDs."""
        valid_ids = [
            'faithful-shepherd-123',
            'blessed-covenant-999',
            'gracious-temple-100',
            'holy-prophet-456'
        ]
        
        for session_id in valid_ids:
            assert SessionIDGenerator.validate_format(session_id), \
                f"Should accept valid ID: {session_id}"
    
    def test_validate_format_invalid_ids(self):
        """Test format validation rejects invalid session IDs."""
        invalid_ids = [
            '',  # Empty
            'faithful-shepherd',  # Missing number
            'faithful-shepherd-12',  # Number too short
            'faithful-shepherd-1234',  # Number too long
            'faithful-shepherd-abc',  # Non-numeric
            'faithful-shepherd-099',  # Number out of range
            'faithful-shepherd-1000',  # Number out of range
            'faithful-123-shepherd',  # Wrong order
            '123-faithful-shepherd',  # Number in wrong position
            'faithful-shepherd-123-extra',  # Too many parts
            '-shepherd-123',  # Missing adjective
            'faithful--123',  # Missing noun
        ]
        
        for session_id in invalid_ids:
            assert not SessionIDGenerator.validate_format(session_id), \
                f"Should reject invalid ID: {session_id}"
    
    def test_generate_without_uniqueness_check(self, temp_word_files):
        """Test generation without uniqueness check (blacklist only)."""
        generator = SessionIDGenerator(
            adjectives_file=temp_word_files['adjectives'],
            nouns_file=temp_word_files['nouns'],
            blacklist_file=temp_word_files['blacklist']
        )
        
        # Generate without uniqueness check
        session_id = generator.generate(uniqueness_check=None)
        
        assert SessionIDGenerator.validate_format(session_id)
        
        # Verify words are not blacklisted
        adjective, noun, _ = session_id.split('-')
        assert adjective not in generator.blacklist
        assert noun not in generator.blacklist
    
    def test_multiple_generations_are_different(self, temp_word_files):
        """Test that multiple generations produce different IDs."""
        generator = SessionIDGenerator(
            adjectives_file=temp_word_files['adjectives'],
            nouns_file=temp_word_files['nouns'],
            blacklist_file=temp_word_files['blacklist']
        )
        
        # Generate multiple IDs
        ids = set()
        for _ in range(20):
            session_id = generator.generate()
            ids.add(session_id)
        
        # Should have generated at least some different IDs
        # (with 100+ adjectives, 100+ nouns, and 900 numbers, collisions are unlikely)
        assert len(ids) > 15, "Should generate mostly unique IDs"
    
    def test_word_list_comments_ignored(self):
        """Test that comments in word list files are ignored."""
        temp_dir = tempfile.mkdtemp()
        
        # Create file with comments
        adj_file = os.path.join(temp_dir, 'adj_with_comments.txt')
        with open(adj_file, 'w') as f:
            f.write('# This is a comment\n')
            f.write('faithful\n')
            f.write('# Another comment\n')
            f.write('blessed\n')
            for i in range(100):
                f.write(f'adj{i}\n')
        
        noun_file = os.path.join(temp_dir, 'nouns.txt')
        with open(noun_file, 'w') as f:
            for i in range(100):
                f.write(f'noun{i}\n')
        
        blacklist_file = os.path.join(temp_dir, 'blacklist.txt')
        with open(blacklist_file, 'w') as f:
            f.write('# Blacklist\n')
            f.write('bad\n')
        
        generator = SessionIDGenerator(
            adjectives_file=adj_file,
            nouns_file=noun_file,
            blacklist_file=blacklist_file
        )
        
        # Comments should not be in word lists
        assert '# This is a comment' not in generator.adjectives
        assert '# Another comment' not in generator.adjectives
        assert '# Blacklist' not in generator.blacklist
        
        # Actual words should be present
        assert 'faithful' in generator.adjectives
        assert 'blessed' in generator.adjectives
        
        # Cleanup
        os.remove(adj_file)
        os.remove(noun_file)
        os.remove(blacklist_file)
        os.rmdir(temp_dir)
