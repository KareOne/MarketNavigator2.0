from utils.logger import bot_logger

class LinkedInBotError(Exception):
    """Base exception class for LinkedIn bot errors"""
    def __init__(self, message: str):
        super().__init__(message)
        bot_logger.error(f"{self.__class__.__name__}: {message}")

class LoginError(LinkedInBotError):
    """Raised when login to LinkedIn fails"""
    pass

class ConnectionError(LinkedInBotError):
    """Raised when connection issues occur"""
    pass

class RateLimitError(LinkedInBotError):
    """Raised when LinkedIn rate limits are hit"""
    pass

class DatabaseError(LinkedInBotError):
    """Raised when database operations fail"""
    pass

class ScrapingError(LinkedInBotError):
    """Raised when scraping operations fail"""
    pass

class APIError(LinkedInBotError):
    """Raised when OpenAI API calls fail"""
    pass

class ElementNotFoundError(LinkedInBotError):
    """Raised when a web element is not found"""
    pass

class ActionBlockedError(LinkedInBotError):
    """Raised when LinkedIn blocks an action"""
    pass
