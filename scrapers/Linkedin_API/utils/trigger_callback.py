import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def switch_to_recaptcha_iframe(driver, timeout=10):
    """Switch to the reCAPTCHA iframe.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: How long to wait for iframe to appear
        
    Returns:
        bool: True if successfully switched to iframe
    """
    try:
        # Wait for iframe to be present and switch to it
        iframe = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[src*='recaptcha']"))
        )
        driver.switch_to.frame(iframe)
        return True
    except TimeoutException:
        print("reCAPTCHA iframe not found")
        return False

def trigger_callback(driver, captcha_response):
    """Inject captcha response and trigger callback.
    
    For reCAPTCHA in iframe, you need to:
    1. Switch back to main content (not iframe)
    2. Inject the response token
    3. Trigger the callback
    """
    # Make sure we're in the main content (not iframe)
    driver.switch_to.default_content()
    
    # Inject the captcha response into the hidden textarea
    driver.execute_script(f'''
        var textarea = document.getElementById("g-recaptcha-response");
        if (textarea) {{
            textarea.innerHTML = "{captcha_response}";
            textarea.value = "{captcha_response}";
            // Make it visible temporarily to trigger validation
            textarea.style.display = "block";
        }}
    ''')
    
    # Trigger the callback if it exists
    driver.execute_script('''
        if (typeof ___grecaptcha_cfg !== 'undefined') {{
            var clients = ___grecaptcha_cfg.clients;
            for (var id in clients) {{
                if (clients[id].callback) {{
                    clients[id].callback("{captcha_response}");
                }}
            }}
        }}
    '''.format(captcha_response=captcha_response))
    
    time.sleep(1)

def find_recaptcha_element(driver):
    """Try to find the g-recaptcha-response element in various ways.
    
    Returns:
        tuple: (found, location) where location is 'main', 'iframe_X', or None
    """
    driver.switch_to.default_content()
    
    # Try 1: Look in main content
    result = driver.execute_script('''
        var textarea = document.getElementById("g-recaptcha-response");
        if (textarea) return "found_in_main";
        
        var textareas = document.getElementsByName("g-recaptcha-response");
        if (textareas.length > 0) return "found_in_main_by_name";
        
        var allTextareas = document.querySelectorAll('textarea[name*="recaptcha"], textarea[id*="recaptcha"]');
        if (allTextareas.length > 0) return "found_similar_in_main";
        
        return null;
    ''')
    
    if result:
        print(f"Found reCAPTCHA element in main content: {result}")
        return True, "main"
    
    # Try 2: Check each iframe
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"Checking {len(iframes)} iframes for g-recaptcha-response element...")
    
    for idx, iframe in enumerate(iframes):
        try:
            driver.switch_to.frame(iframe)
            result = driver.execute_script('''
                var textarea = document.getElementById("g-recaptcha-response");
                if (textarea) return true;
                return false;
            ''')
            
            if result:
                print(f"Found g-recaptcha-response in iframe {idx}")
                driver.switch_to.default_content()
                return True, f"iframe_{idx}"
            
            driver.switch_to.default_content()
        except Exception as e:
            print(f"Error checking iframe {idx}: {e}")
            driver.switch_to.default_content()
            continue
    
    print("g-recaptcha-response element not found anywhere")
    return False, None

def solve_recaptcha_in_iframe(driver, captcha_response):
    """Complete flow to solve reCAPTCHA in iframe.
    
    Args:
        driver: Selenium WebDriver instance
        captcha_response: The solved captcha token
        
    Returns:
        bool: True if successfully solved
    """
    try:
        # Step 1: Find where the element is
        found, location = find_recaptcha_element(driver)
        
        if not found:
            print("ERROR: g-recaptcha-response element not found")
            print("Trying alternative approach...")
            return solve_recaptcha_alternative(driver, captcha_response)
        
        # Step 2: Make sure we're in main content
        driver.switch_to.default_content()
        
        # Step 3: Try multiple methods to inject the response token
        methods_tried = []
        
        # Method 1: By ID
        success = driver.execute_script('''
            var textarea = document.getElementById("g-recaptcha-response");
            if (textarea) {
                textarea.innerHTML = arguments[0];
                textarea.value = arguments[0];
                textarea.style.display = "block";
                return true;
            }
            return false;
        ''', captcha_response)
        methods_tried.append(("By ID", success))
        
        # Method 2: By Name
        if not success:
            success = driver.execute_script('''
                var textareas = document.getElementsByName("g-recaptcha-response");
                if (textareas.length > 0) {
                    textareas[0].innerHTML = arguments[0];
                    textareas[0].value = arguments[0];
                    textareas[0].style.display = "block";
                    return true;
                }
                return false;
            ''', captcha_response)
            methods_tried.append(("By Name", success))
        
        # Method 3: Query selector
        if not success:
            success = driver.execute_script('''
                var textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
                if (!textarea) {
                    textarea = document.querySelector('textarea[id="g-recaptcha-response"]');
                }
                if (textarea) {
                    textarea.innerHTML = arguments[0];
                    textarea.value = arguments[0];
                    textarea.style.display = "block";
                    return true;
                }
                return false;
            ''', captcha_response)
            methods_tried.append(("Query Selector", success))
        
        print(f"Injection methods tried: {methods_tried}")
        
        if not success:
            print("All injection methods failed!")
            return False
        
        # Step 4: Trigger the callback and verification
        print("Triggering reCAPTCHA callbacks...")
        callback_result = driver.execute_script('''
            var token = arguments[0];
            var callbacksTriggered = 0;
            
            // Method 1: Trigger through ___grecaptcha_cfg
            if (typeof ___grecaptcha_cfg !== 'undefined') {
                var clients = ___grecaptcha_cfg.clients;
                for (var id in clients) {
                    if (clients[id] && clients[id].callback) {
                        console.log("Triggering callback for client:", id);
                        try {
                            clients[id].callback(token);
                            callbacksTriggered++;
                        } catch(e) {
                            console.error("Error triggering callback:", e);
                        }
                    }
                }
            }
            
            // Method 2: Dispatch events on the textarea
            var textarea = document.getElementById("g-recaptcha-response");
            if (textarea) {
                var events = ['input', 'change'];
                events.forEach(function(eventType) {
                    var event = new Event(eventType, { bubbles: true, cancelable: true });
                    textarea.dispatchEvent(event);
                });
            }
            
            // Method 3: Try to find and enable submit button
            var submitButtons = document.querySelectorAll('button[type="submit"], input[type="submit"]');
            submitButtons.forEach(function(btn) {
                if (btn.disabled) {
                    btn.disabled = false;
                    console.log("Enabled submit button:", btn);
                }
            });
            
            // Method 4: Set data-callback attribute if exists
            var recaptchaDiv = document.querySelector('.g-recaptcha');
            if (recaptchaDiv) {
                var callback = recaptchaDiv.getAttribute('data-callback');
                if (callback && typeof window[callback] === 'function') {
                    console.log("Calling data-callback function:", callback);
                    try {
                        window[callback](token);
                        callbacksTriggered++;
                    } catch(e) {
                        console.error("Error calling data-callback:", e);
                    }
                }
            }
            
            return {
                callbacksTriggered: callbacksTriggered,
                hasGrecaptcha: typeof grecaptcha !== 'undefined',
                submitButtonsFound: submitButtons.length
            };
        ''', captcha_response)
        
        print(f"Callback trigger result: {callback_result}")
        print(f"Callbacks triggered: {callback_result.get('callbacksTriggered', 0)}")
        
        # Step 5: Wait a moment and verify the response is still there
        time.sleep(1)
        
        verified = driver.execute_script('''
            var textarea = document.getElementById("g-recaptcha-response");
            if (textarea && textarea.value) {
                return textarea.value.length > 0;
            }
            return false;
        ''')
        
        if verified:
            print("✅ reCAPTCHA response verified in textarea")
        else:
            print("⚠️ reCAPTCHA response not found in textarea after injection")
        
        print("reCAPTCHA response injected successfully")
        time.sleep(2)
        return True
        
    except Exception as e:
        print(f"Error solving reCAPTCHA in iframe: {e}")
        import traceback
        traceback.print_exc()
        # Make sure to switch back to main content even if error occurs
        driver.switch_to.default_content()
        return False

def solve_and_submit_recaptcha(driver, captcha_response, auto_submit=True, submit_selector=None):
    """Complete flow: inject token, trigger callbacks, verify, and optionally submit.
    
    Args:
        driver: Selenium WebDriver instance
        captcha_response: The solved captcha token
        auto_submit: Whether to automatically submit the form after solving
        submit_selector: Optional CSS selector for submit button
        
    Returns:
        dict: Result with success status and details
    """
    result = {
        'success': False,
        'token_injected': False,
        'callbacks_triggered': 0,
        'verified': False,
        'submitted': False,
        'error': None
    }
    
    try:
        # Step 1: Inject the token
        print("Step 1: Injecting reCAPTCHA token...")
        if solve_recaptcha_in_iframe(driver, captcha_response):
            result['token_injected'] = True
            print("✅ Token injected")
        else:
            result['error'] = "Failed to inject token"
            print("❌ Failed to inject token")
            return result
        
        # Step 2: Verify the token is present
        print("\nStep 2: Verifying token...")
        status = verify_recaptcha_solved(driver)
        result['verified'] = status.get('textareaHasValue', False)
        
        if not result['verified']:
            result['error'] = "Token not found in textarea after injection"
            print("❌ Verification failed")
            return result
        
        print("✅ Token verified")
        
        # Step 3: Submit if requested
        if auto_submit:
            print("\nStep 3: Submitting form...")
            
            # Try clicking submit button first
            if click_submit_button(driver, submit_selector):
                result['submitted'] = True
                print("✅ Form submitted via button click")
            else:
                # Fall back to manual form submission
                if manual_submit_form(driver):
                    result['submitted'] = True
                    print("✅ Form submitted via JavaScript")
                else:
                    print("⚠️ Could not auto-submit form - you may need to click submit manually")
            
            time.sleep(2)
        
        result['success'] = result['token_injected'] and result['verified']
        
        print("\n" + "="*60)
        print("FINAL RESULT:")
        print(f"  Token Injected: {result['token_injected']}")
        print(f"  Verified: {result['verified']}")
        print(f"  Submitted: {result['submitted']}")
        print(f"  Success: {result['success']}")
        print("="*60 + "\n")
        
        return result
        
    except Exception as e:
        result['error'] = str(e)
        print(f"❌ Error in solve_and_submit_recaptcha: {e}")
        import traceback
        traceback.print_exc()
        return result

def solve_recaptcha_alternative(driver, captcha_response):
    """Alternative method when g-recaptcha-response element is not found.
    
    This creates the element if it doesn't exist.
    """
    try:
        driver.switch_to.default_content()
        
        print("Attempting to create g-recaptcha-response element...")
        success = driver.execute_script('''
            // Try to find the recaptcha div
            var recaptchaDiv = document.querySelector('.g-recaptcha');
            if (!recaptchaDiv) {
                recaptchaDiv = document.querySelector('[data-sitekey]');
            }
            
            if (recaptchaDiv) {
                // Create the textarea if it doesn't exist
                var textarea = document.getElementById("g-recaptcha-response");
                if (!textarea) {
                    textarea = document.createElement("textarea");
                    textarea.id = "g-recaptcha-response";
                    textarea.name = "g-recaptcha-response";
                    textarea.className = "g-recaptcha-response";
                    textarea.style.display = "none";
                    recaptchaDiv.appendChild(textarea);
                    console.log("Created g-recaptcha-response element");
                }
                
                // Set the value
                textarea.innerHTML = arguments[0];
                textarea.value = arguments[0];
                
                // Trigger callback
                if (typeof ___grecaptcha_cfg !== 'undefined') {
                    var clients = ___grecaptcha_cfg.clients;
                    for (var id in clients) {
                        if (clients[id] && clients[id].callback) {
                            clients[id].callback(arguments[0]);
                        }
                    }
                }
                
                return true;
            }
            
            return false;
        ''', captcha_response)
        
        if success:
            print("Alternative method succeeded!")
            time.sleep(2)
            return True
        else:
            print("Alternative method failed - no recaptcha container found")
            return False
            
    except Exception as e:
        print(f"Alternative method error: {e}")
        driver.switch_to.default_content()
        return False

def get_recaptcha_iframe_info(driver):
    """Debug helper to get information about reCAPTCHA iframes on the page.
    
    Returns:
        list: Information about each iframe found
    """
    driver.switch_to.default_content()
    
    iframes_info = []
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    
    for idx, iframe in enumerate(iframes):
        info = {
            'index': idx,
            'src': iframe.get_attribute('src'),
            'title': iframe.get_attribute('title'),
            'name': iframe.get_attribute('name'),
            'id': iframe.get_attribute('id'),
        }
        iframes_info.append(info)
        print(f"Iframe {idx}: {info}")
    
    return iframes_info

def click_submit_button(driver, button_selector=None):
    """Find and click the submit button after captcha is solved.
    
    Args:
        driver: Selenium WebDriver instance
        button_selector: Optional specific selector for submit button
        
    Returns:
        bool: True if button was clicked
    """
    try:
        driver.switch_to.default_content()
        
        if button_selector:
            # Use provided selector
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, button_selector))
            )
            button.click()
            print(f"✅ Clicked submit button: {button_selector}")
            return True
        
        # Try common submit button patterns
        selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button.submit',
            'button#submit',
            'button[name="submit"]',
            'form button:last-child',
        ]
        
        for selector in selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        print(f"✅ Clicked submit button with selector: {selector}")
                        time.sleep(1)
                        return True
            except Exception as e:
                continue
        
        print("⚠️ No submit button found or clicked")
        return False
        
    except Exception as e:
        print(f"Error clicking submit button: {e}")
        return False

def verify_recaptcha_solved(driver):
    """Check if reCAPTCHA has been successfully solved.
    
    Returns:
        dict: Status information about the captcha
    """
    try:
        driver.switch_to.default_content()
        
        status = driver.execute_script('''
            var result = {
                textareaExists: false,
                textareaHasValue: false,
                textareaValue: '',
                tokenLength: 0,
                checkboxChecked: false,
                hasError: false,
            };
            
            // Check textarea
            var textarea = document.getElementById("g-recaptcha-response");
            if (textarea) {
                result.textareaExists = true;
                result.textareaValue = textarea.value;
                result.tokenLength = textarea.value.length;
                result.textareaHasValue = textarea.value.length > 0;
            }
            
            // Check for reCAPTCHA success indicators
            var recaptchaDiv = document.querySelector('.g-recaptcha');
            if (recaptchaDiv) {
                // Check for error messages
                var errorMsg = recaptchaDiv.querySelector('.recaptcha-error-message');
                if (errorMsg && errorMsg.textContent) {
                    result.hasError = true;
                }
            }
            
            // Check for grecaptcha response
            if (typeof grecaptcha !== 'undefined') {
                try {
                    var response = grecaptcha.getResponse();
                    if (response) {
                        result.checkboxChecked = true;
                        result.grecaptchaResponse = response;
                    }
                } catch(e) {
                    console.log("Could not get grecaptcha response:", e);
                }
            }
            
            return result;
        ''')
        
        print("\n" + "="*60)
        print("RECAPTCHA VERIFICATION STATUS")
        print("="*60)
        print(f"Textarea exists: {status['textareaExists']}")
        print(f"Textarea has value: {status['textareaHasValue']}")
        print(f"Token length: {status['tokenLength']}")
        print(f"Checkbox checked: {status['checkboxChecked']}")
        print(f"Has error: {status['hasError']}")
        
        if status['textareaHasValue']:
            print(f"Token preview: {status['textareaValue'][:50]}...")
        
        print("="*60 + "\n")
        
        return status
        
    except Exception as e:
        print(f"Error verifying captcha: {e}")
        return {}

def manual_submit_form(driver):
    """Manually submit the form using JavaScript.
    
    Returns:
        bool: True if form was submitted
    """
    try:
        driver.switch_to.default_content()
        
        result = driver.execute_script('''
            // Find the form containing the recaptcha
            var textarea = document.getElementById("g-recaptcha-response");
            if (!textarea) return {success: false, message: "No textarea found"};
            
            var form = textarea.closest('form');
            if (!form) return {success: false, message: "No form found"};
            
            // Try to submit the form
            try {
                form.submit();
                return {success: true, message: "Form submitted via form.submit()"};
            } catch(e) {
                // If form.submit() fails, try clicking submit button
                var submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitBtn) {
                    submitBtn.click();
                    return {success: true, message: "Form submitted via button click"};
                }
                return {success: false, message: "Could not submit form: " + e.message};
            }
        ''')
        
        print(f"Form submission result: {result}")
        time.sleep(2)
        return result.get('success', False)
        
    except Exception as e:
        print(f"Error manually submitting form: {e}")
        return False

def debug_recaptcha_page(driver, save_html=True):
    """Comprehensive debug information about reCAPTCHA on the page.
    
    Args:
        driver: Selenium WebDriver instance
        save_html: Whether to save the page HTML for inspection
        
    Returns:
        dict: Debug information
    """
    driver.switch_to.default_content()
    
    debug_info = {
        'url': driver.current_url,
        'title': driver.title,
        'iframes': [],
        'recaptcha_elements': [],
        'recaptcha_scripts': [],
    }
    
    print("\n" + "="*60)
    print("RECAPTCHA DEBUG INFORMATION")
    print("="*60)
    print(f"URL: {driver.current_url}")
    print(f"Title: {driver.title}")
    
    # Check for reCAPTCHA elements
    recaptcha_info = driver.execute_script('''
        var info = {
            hasGrecaptcha: typeof grecaptcha !== 'undefined',
            hasGrecaptchaCfg: typeof ___grecaptcha_cfg !== 'undefined',
            recaptchaElements: [],
            recaptchaTextareas: [],
            recaptchaDivs: [],
        };
        
        // Find divs with recaptcha classes or data attributes
        var divs = document.querySelectorAll('[class*="recaptcha"], [id*="recaptcha"], [data-sitekey]');
        divs.forEach(function(div) {
            info.recaptchaDivs.push({
                tagName: div.tagName,
                id: div.id,
                className: div.className,
                sitekey: div.getAttribute('data-sitekey'),
            });
        });
        
        // Find textareas
        var textareas = document.querySelectorAll('textarea[name*="recaptcha"], textarea[id*="recaptcha"]');
        textareas.forEach(function(ta) {
            info.recaptchaTextareas.push({
                id: ta.id,
                name: ta.name,
                className: ta.className,
                value: ta.value,
            });
        });
        
        // Get grecaptcha config if available
        if (typeof ___grecaptcha_cfg !== 'undefined') {
            info.clientIds = Object.keys(___grecaptcha_cfg.clients || {});
        }
        
        return info;
    ''')
    
    print(f"\ngrecaptcha object exists: {recaptcha_info['hasGrecaptcha']}")
    print(f"___grecaptcha_cfg exists: {recaptcha_info['hasGrecaptchaCfg']}")
    
    if recaptcha_info.get('clientIds'):
        print(f"reCAPTCHA client IDs: {recaptcha_info['clientIds']}")
    
    print(f"\nFound {len(recaptcha_info['recaptchaDivs'])} reCAPTCHA divs:")
    for div in recaptcha_info['recaptchaDivs']:
        print(f"  - {div}")
    
    print(f"\nFound {len(recaptcha_info['recaptchaTextareas'])} reCAPTCHA textareas:")
    for ta in recaptcha_info['recaptchaTextareas']:
        print(f"  - {ta}")
    
    debug_info['recaptcha_elements'] = recaptcha_info
    
    # Check iframes
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"\nFound {len(iframes)} iframes:")
    
    for idx, iframe in enumerate(iframes):
        iframe_info = {
            'index': idx,
            'src': iframe.get_attribute('src'),
            'title': iframe.get_attribute('title'),
            'name': iframe.get_attribute('name'),
            'id': iframe.get_attribute('id'),
        }
        debug_info['iframes'].append(iframe_info)
        print(f"  {idx}. {iframe_info}")
        
        # Try to check inside iframe
        try:
            driver.switch_to.frame(iframe)
            has_textarea = driver.execute_script('''
                return document.getElementById("g-recaptcha-response") !== null;
            ''')
            if has_textarea:
                print(f"     ⭐ Contains g-recaptcha-response element!")
            driver.switch_to.default_content()
        except Exception as e:
            print(f"     ⚠️ Could not access iframe: {e}")
            driver.switch_to.default_content()
    
    # Save HTML if requested
    if save_html:
        try:
            timestamp = int(time.time())
            filename = f"recaptcha_debug_{timestamp}.html"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print(f"\n💾 Page HTML saved to: {filename}")
            debug_info['html_file'] = filename
        except Exception as e:
            print(f"\n⚠️ Could not save HTML: {e}")
    
    print("="*60 + "\n")
    
    return debug_info