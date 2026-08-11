import urllib.parse


def generate_image(prompt):
    if not prompt:
        prompt = "international news"
    clean_prompt = urllib.parse.quote(prompt + ", realistic professional news photography")
    return f"[https://image.pollinations.ai/prompt/](https://image.pollinations.ai/prompt/){clean_prompt}"
