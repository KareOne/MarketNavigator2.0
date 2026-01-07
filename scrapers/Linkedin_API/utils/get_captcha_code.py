from twocaptcha import TwoCaptcha
from utils.logger import bot_logger

def get_captcha_code(current_url: str) -> str | None:
    api_key = '8b647e586b20c108fce15761aa8a3b2b'
    solver = TwoCaptcha(api_key)

    try:        
        # Solve the captcha
        result = solver.recaptcha(
            sitekey='6LcIy_MqAAAAAMKiupFSbmzW3xjGSlIfRzNWYMjC',
            url=current_url)
        
        captcha_response = result["code"]
        
        return captcha_response
    except Exception as e:
        bot_logger.error(f"Error solving captcha: {e}")
        return False