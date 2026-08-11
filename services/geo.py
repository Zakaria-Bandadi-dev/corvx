import ipaddress

import requests
from flask import request

from config.settings import COUNTRIES, LANGUAGES


def get_client_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.remote_addr
    return ip


def detect_country():
    saved_country = request.cookies.get("country")
    if saved_country in COUNTRIES:
        return saved_country

    try:
        ip = get_client_ip()
        try:
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                return "ma"
        except Exception:
            pass

        response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=3)
        if response.ok:
            data = response.json()
            country_code = data.get("country_code", "").lower()
            if country_code in COUNTRIES:
                return country_code

    except Exception as e:
        print(f"!! Country detection failed: {e}")

    return "ma"


def detect_language(country):
    saved_language = request.cookies.get("lang")
    if saved_language in LANGUAGES:
        return saved_language

    accept_language = request.headers.get("Accept-Language", "").lower()
    for language in LANGUAGES:
        if accept_language.startswith(language):
            return language

    if country in COUNTRIES:
        languages = COUNTRIES[country]["languages"]
        if languages:
            for language in languages:
                if language in LANGUAGES:
                    return language

    return "en"
