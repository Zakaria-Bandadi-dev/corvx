from groq import Groq

from config.settings import (
    NEWS_GROQ_KEYS,
    GROQ_MODEL,
    SEO_GROQ_MODEL,
)


current_groq_key = 0


def generate_with_groq(prompt):
    global current_groq_key

    if not NEWS_GROQ_KEYS:
        print("!! NO GROQ API KEYS FOUND (news)")
        return None

    total_keys = len(NEWS_GROQ_KEYS)

    for attempt in range(total_keys):
        key_index = current_groq_key
        api_key = NEWS_GROQ_KEYS[key_index]

        print(
            f"-> Using Groq API "
            f"#{key_index + 1}/{total_keys}"
        )

        try:
            client = Groq(api_key=api_key)

            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional international news writer.\n\n"
                            "Your job is to transform real news topics into "
                            "clear, neutral and informative news articles.\n\n"
                            "IMPORTANT:\n"
                            "Do NOT turn every topic into an AI article.\n"
                            "Write about the actual subject.\n"
                            "If the topic is politics, explain the political event.\n"
                            "If the topic is sports, explain the sports event.\n"
                            "If the topic is economy, explain the economy event.\n"
                            "If the topic is technology, explain the technology event.\n"
                            "Do not invent names, numbers or facts.\n"
                            "Do not claim information that is not supported by the source.\n\n"
                            "Keep the article readable for normal users."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0.35,
                max_tokens=1200,
            )

            result = response.choices[0].message.content

            if not result:
                raise Exception("Empty Groq response")

            print(
                f"-> Groq API "
                f"#{key_index + 1} SUCCESS"
            )

            current_groq_key = (
                current_groq_key + 1
            ) % total_keys

            return result.strip()

        except Exception as e:
            error = str(e)

            print(
                f"!! Groq API "
                f"#{key_index + 1} FAILED: {error}"
            )

            current_groq_key = (
                current_groq_key + 1
            ) % total_keys

            if (
                "429" in error
                or "rate_limit" in error.lower()
            ):
                print(
                    f"!! API "
                    f"#{key_index + 1} RATE LIMITED"
                )

            # Try the next available key.
            continue

    print("!! ALL GROQ KEYS FAILED")

    return None


def generate_with_groq_compound(
    prompt,
    max_tokens=2000,
):
    global current_groq_key

    if not NEWS_GROQ_KEYS:
        print("!! NO GROQ API KEYS FOUND (compound)")
        return None

    total = len(NEWS_GROQ_KEYS)

    for attempt in range(total):
        key_index = current_groq_key
        api_key = NEWS_GROQ_KEYS[key_index]

        print(
            f"-> Using Compound Groq API "
            f"#{key_index + 1}/{total}"
        )

        try:
            client = Groq(api_key=api_key)

            response = client.chat.completions.create(
                model=SEO_GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a web research and SEO intelligence agent. "
                            "Use web_search and visit_website when available. "
                            "Never invent search data, rankings, facts, or sources. "
                            "Clearly distinguish observed web evidence from inference. "
                            "Return only valid JSON when requested."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                compound_custom={
                    "tools": {
                        "enabled_tools": [
                            "web_search",
                            "visit_website",
                        ]
                    }
                },
                temperature=0.15,
                max_tokens=max_tokens,
            )

            result = response.choices[0].message.content

            if not result:
                raise Exception("Empty Compound response")

            print(
                f"-> Compound Groq API "
                f"#{key_index + 1} SUCCESS"
            )

            current_groq_key = (
                current_groq_key + 1
            ) % total

            return result.strip()

        except Exception as e:
            error = str(e)

            print(
                f"!! Compound SEO research failed "
                f"with key #{key_index + 1}: {error}"
            )

            current_groq_key = (
                current_groq_key + 1
            ) % total

            if (
                "429" in error
                or "rate_limit" in error.lower()
            ):
                print(
                    f"!! Compound API "
                    f"#{key_index + 1} RATE LIMITED"
                )

            # Try the next available key.
            continue

    print("!! ALL COMPOUND GROQ KEYS FAILED")

    return None
