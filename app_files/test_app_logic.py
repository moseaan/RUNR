import unittest
import os
import sys

# Assume config.py is in the parent directory or adjust path as needed
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import CATEGORY_MAPPING
except ImportError:
    print("Could not import CATEGORY_MAPPING from config.py. Make sure it exists.")
    CATEGORY_MAPPING = {} # Define empty for tests to run without error

class TestConfigMappings(unittest.TestCase):

    def test_instagram_likes_mapping(self):
        """Tests if the mapping for Instagram Likes exists and is correct."""
        if not CATEGORY_MAPPING:
            self.skipTest("CATEGORY_MAPPING not loaded.")
            
        key = ("Instagram", "Likes")
        expected_value = "Instagram - Likes - [RECOMMENDED]"
        self.assertIn(key, CATEGORY_MAPPING, f"Key {key} not found in CATEGORY_MAPPING.")
        self.assertEqual(CATEGORY_MAPPING[key], expected_value)

    def test_mapping_lookup_success(self):
        """Tests successful lookup for a known key."""
        if not CATEGORY_MAPPING:
            self.skipTest("CATEGORY_MAPPING not loaded.")
            
        key = ("Instagram", "Likes")
        value = CATEGORY_MAPPING.get(key)
        self.assertIsNotNone(value, f"Value for key {key} should not be None.")
        self.assertEqual(value, "Instagram - Likes - [RECOMMENDED]")

    def test_mapping_lookup_failure(self):
        """Tests lookup failure for an unknown key."""
        if not CATEGORY_MAPPING:
            self.skipTest("CATEGORY_MAPPING not loaded.")
            
        key = ("NonExistentPlatform", "NonExistentService")
        value = CATEGORY_MAPPING.get(key)
        self.assertIsNone(value, f"Value for non-existent key {key} should be None.")

# Add more tests for other mappings or UI logic if desired

if __name__ == '__main__':
    unittest.main() 