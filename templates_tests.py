from django.test import TestCase, RequestFactory
from django.contrib.messages import add_message, get_messages
from django.contrib.messages import constants as message_constants
from django.contrib.sessions.middleware import SessionMiddleware
from django.template import Context, Template
from django.http import HttpResponse


class MessageTemplateSecurityTests(TestCase):
    """Test that the messages template properly escapes HTML/JavaScript"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
    def add_session_to_request(self, request):
        """Helper to add session to request"""
        middleware = SessionMiddleware(lambda x: HttpResponse())
        middleware.process_request(request)
        request.session.save()
        
    def test_message_template_escapes_html(self):
        """Test that HTML in messages is escaped"""
        request = self.factory.get('/')
        self.add_session_to_request(request)
        
        # Add a message with HTML
        add_message(request, message_constants.INFO, '<script>alert("XSS")</script>')
        
        # Get the messages
        messages = list(get_messages(request))
        self.assertEqual(len(messages), 1)
        
        # Render the template
        template = Template('{% load static %}{% for message in messages %}{{ message }}{% endfor %}')
        context = Context({'messages': messages, 'DEFAULT_MESSAGE_LEVELS': message_constants})
        rendered = template.render(context)
        
        # Verify that the HTML is escaped
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        
    def test_message_template_escapes_javascript(self):
        """Test that JavaScript in messages is escaped"""
        request = self.factory.get('/')
        self.add_session_to_request(request)
        
        # Add a message with JavaScript
        add_message(request, message_constants.ERROR, '<img src=x onerror="alert(1)">')
        
        messages = list(get_messages(request))
        template = Template('{% for message in messages %}{{ message }}{% endfor %}')
        context = Context({'messages': messages})
        rendered = template.render(context)
        
        # Verify that the HTML is escaped
        self.assertNotIn('onerror=', rendered)
        
    def test_message_template_preserves_safe_text(self):
        """Test that regular text messages are displayed correctly"""
        request = self.factory.get('/')
        self.add_session_to_request(request)
        
        # Add a regular message
        add_message(request, message_constants.INFO, 'This is a safe message')
        
        messages = list(get_messages(request))
        template = Template('{% for message in messages %}{{ message }}{% endfor %}')
        context = Context({'messages': messages})
        rendered = template.render(context)
        
        # Verify the message is displayed correctly
        self.assertIn('This is a safe message', rendered)
