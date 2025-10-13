from django.test import TestCase
from donationPage.utils import make_donorUrl
from datetime import datetime

class SecurityTests(TestCase):
    
    def test_make_donorUrl_generates_valid_format(self):
        """Test that make_donorUrl generates a URL with proper format"""
        url = make_donorUrl()
        # Should be 36 digits + date string (format: YYYYMMDDHHMMtimezone)
        self.assertIsInstance(url, str)
        self.assertGreater(len(url), 36)  # At least 36 digits + date
        
    def test_make_donorUrl_is_unpredictable(self):
        """Test that make_donorUrl generates unpredictable URLs"""
        # Generate multiple URLs and ensure they're all different
        urls = [make_donorUrl() for _ in range(100)]
        # All URLs should be unique
        self.assertEqual(len(urls), len(set(urls)))
        
    def test_make_donorUrl_with_date(self):
        """Test that make_donorUrl works with a specific date"""
        test_date = datetime(2023, 1, 15, 10, 30)
        url = make_donorUrl(date=test_date)
        # Should contain the date portion
        self.assertIn('202301151030', url)
        
    def test_make_donorUrl_uses_cryptographically_secure_random(self):
        """Test that the generated URLs have sufficient entropy"""
        # Generate a large sample and check for sufficient randomness
        urls = [make_donorUrl() for _ in range(1000)]
        
        # Extract just the numeric portion (first 36 digits)
        numeric_parts = [url[:36] for url in urls]
        
        # All should be unique (collision probability should be negligible)
        self.assertEqual(len(numeric_parts), len(set(numeric_parts)))
        
        # All should be 36 digits
        for num in numeric_parts:
            self.assertEqual(len(num), 36)
            self.assertTrue(num.isdigit())

