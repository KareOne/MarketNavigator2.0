from twocaptcha import TwoCaptcha
import requests
import json

def calculate_captcha():
    api_key = '8b647e586b20c108fce15761aa8a3b2b'
    solver = TwoCaptcha(api_key)
    try:
        result = solver.recaptcha(
            sitekey='6LeeN1sqAAAAAEJuX1Xq4tUU6RFkSWr6FmlWAntc',
            url='https://tracxn.com/signup')
        
        code = str(result["code"])
        print('solved: ' + code)
        return code
    except Exception as e:
        print(e)

def send_request(email: str, captcha_code: str, cookie_string: str):

    url = "https://platform.tracxn.com/auth/otp/signup"

    payload = json.dumps({
        "username": email
    })
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        'X-Captcha-Response': 'ei:'+captcha_code,
        'Cookie': cookie_string
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    try:

        resp = response.json()

        if "errorCode" in resp:
            return None

        return resp
    
    except:
        return None

def test_request():

    url = "https://platform.tracxn.com/auth/otp/signup"

    payload = json.dumps({
    "username": "tg@dfcx.com"
    })
    headers = {
    'Content-Type': 'application/json',
    'User-Agent': 'PostmanRuntime/7.51.0',
    'X-Captcha-Response': 'ei:0cAFcWeA7k6dJ2DtnhacdcDY-HIuB2hVO3JlwDNf6p64_LgdQIrNP3XjF8nG2JUfW2QrfaeQkc1kH2V74KuZ9v6YKigTql3ZWVKE4TV6iFsKj1GyOgsjQ-3rZa1Dc27NL2x504HWtKsqo-hElEnDKtQ-7K04X89ROfIoMVyF6Z4BB1RhwNWh2W_6PZdC8T5_S2g92OkSd0E-aUVwhhvuYYaMabeIX47zdWeTn3jhPbdN8AVEShCauzjJsMSyk6WDbGrafFzRgFK7WScQHCA0rUM1hZfE7ZZtLJZPAqLkhBtKh8DFuptkzLHCtv8cxsO-h0qxMLu8JSrIDmez-lCMo2I3msHdrLZ0heEyWxa1gFs19lYEENiFDMdXr-_BrpoCSUaf7T6YCXmb670dxIudeA_0VVSLQrk9Ua0cOQWk0y-yJhTplT4ByOt7LWe8gs_ks7-M0v7Lv5Rp6kuuTz2uRtZIfjqgbGmvrre-kGopQM7kEXJEjeaY5Ag9ancFo-S4UGxTDYtDxnrOg9z9Wcuxrmy3wSkYA1q7umzfSBQxH936uBPEHHvDEjDeqDL8-XkBmSPEEJptPtIhPHkbBhZa9iRsrXEz23Lq6Oa-7ToLmpDT8075thCSEgl7bNhLUPPy20hwXP2DTUJpoEwE3a6YuCLh9bKXhKkHJjwADi__TodYBdd63P6JSGX5QWyWCBPWFhBM32o_AnKMcTzaLhRH0KSNpMlWu_bDIPrxG7m-fTPrPORWGP_zJWHNZNPTiYu8Dd5_KtafHycniWBxOngKf5G_HZ2aI4zCY5idST-XVZaUGIx1oauemKcfsrl3fE1Hmr_qoI4IbAZy9QUrV6VowgdOntkGN2q7L1dbO4R9qylbaVh5MP40E5GRgMT78gzC1yFL4s_mi4Y1pAdyUS2eEGWsEU2gBQtY-9Tf4lYJ7cGUqZteBJc0kijZ3-qAerDAgLX9r0fAZreoBJ8_9EENVFnLpvT1MG-4FsGkqFkm6BEnGUYkT82czvIho0j3i_C_hR64i5A-fzdsZSjkoLng3Pb2YRZTeAP0xbNDhM-1b8FHEYN-vPcoTEIwXBOzC9HKyFQjfrPFryOacVYW0AlFFWq0aGJBqELymOiLdjxSDXALSsZgR5KPFxHkkJpeUSQm_379ckqpTF6aN-qFXeu5el-Kom-4T1Q4QFe5YVurctO6gVUXrRKyHrWFx0KDnS2gN3_-LAid9f1T-ape4s_FQS1duNpGe7i2HranQl6BcNshzHFE5fcwe7_wz-BLwBYYRnhdS6MBHXG5LgbC4Ls7YGgluF_J1cNze4gnrU50oTaex--k5nG3syOBkpU01ZIOJvJ7kDVr9l6a-GeqFmVbl4rvYLq4OzoztilX3NdsWthd8P0Rsy7zf03wPAEuU6HsdRziAuRAszg0VqutJenGWRWyE-Nks4uB5KfxPi9uc33qvBs2jSTha4LhHOYNFKr61opGmbjhq62C_ypPR4zHJz8AWitlcTKg-j96z5CNgj95qSXEb9iyjV578WOVq56g9isA4nzRFIVinNziqNBjEfk4Xxs31XeZPl2ovWUwhOwOIZLUsI0uMGzp_mqbgszeEy-HNwikKaj7oGrdgG0eTHBMfzv3Aew6EDRn0nbNBD0r-3BDZBT2bjxLTkaWl8SfyPTjCF6U61MGNyrVaN56zbRiblLNKGsFM8oYn9hzfocDvOQq_d6CV7jxEm7bh8uYsS3RQABSHm8sG7MTXOZCw4OEYiKgiHbH_lrCc1OSfWIwonC40GFoZrHSlCzdv5xqU92l-PQJQq0qBz',
    'Cookie': 'st=b2c8b214-6b7a-4cc3-bca4-8c17f4bfc177; AID=b2c8b2146b7a3cc3fca48c17f4bfc1774e5e2841ecbdadd5a8657ab676473948:b2c8b2146b7a3cc3fca48c17f4bfc1774e5e2841ecbdadd5a8657ab676473948; _ga_63RZ0E5CHG=GS2.1.s1765831962$o1$g0$t1765831962$j60$l0$h0; _ga=GA1.1.1509787402.1765831962'
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)
