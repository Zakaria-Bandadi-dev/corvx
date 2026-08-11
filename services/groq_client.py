from groq import Groq

import state
from config.settings import (
    NEWS_GROQ_KEYS,
    JOB_GROQ_KEYS,
    GROQ_MODEL,
    JOBS_GROQ_MODEL,
    SEO_GROQ_MODEL,
)

JOBS_SYSTEM_PROMPT = """أنت مساعد كيقلب على عروض الخدمة الحقيقية فالمواقع الرسمية.
خاصك تستعمل الأدوات المتوفرة عندك (web_search و visit_website) باش تدخل
للموقع المعطى وتلقى آخر 5 إلى 10 عروض خدمة جداد الموجودين فيه دابا.

لكل عرض، رجع المعلومات التالية بالعربية فقط (حتى ولو كان الموقع الأصلي
بالفرنسية ولا بالإنجليزية، ترجم/لخص بالعربية):

- title_ar: عنوان المنصب
- company_ar: اسم الشركة أو المؤسسة
- description_ar: ملخص قصير للمهمة
- conditions_ar: الشروط (المستوى الدراسي، الديبلوم، التجربة، الحرفة...)
- documents_ar: الوثائق المطلوبة للترشيح (CV، ديبلوم، CIN، رسالة تحفيزية...)
- how_to_apply_ar: كيفاش تدير الترشيح بالضبط، خطوة بخطوة
- deadline: آخر أجل للترشيح إلا كان مذكور، وإلا اكتب "غير محدد"
- source_url: الرابط المباشر ديال العرض إلا قدرتي تلقاه

رجع الجواب فقط كـ JSON array صحيح، بلا أي شرح، بلا Markdown، بهاد الشكل بالضبط:

[
  {
    "title_ar": "...",
    "company_ar": "...",
    "description_ar": "...",
    "conditions_ar": "...",
    "documents_ar": "...",
    "how_to_apply_ar": "...",
    "deadline": "...",
    "source_url": "..."
  }
]

إلا ما لقيتيش عروض جداد، رجع array فارغ: []
"""


def generate_with_groq(prompt):
    """News article generation / translation model (rotates over NEWS_GROQ_KEYS)."""
    if not NEWS_GROQ_KEYS:
        print("!! NO GROQ API KEYS FOUND (news)")
        return None

    total_keys = len(NEWS_GROQ_KEYS)

    for _ in range(total_keys):
        key_index = state.current_groq_key
        api_key = NEWS_GROQ_KEYS[key_index]
        print(f"-> Using Groq API #{key_index + 1}/{total_keys}")

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
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.35,
                max_tokens=1200
            )

            result = response.choices[0].message.content
            if not result:
                raise Exception("Empty Groq response")

            print(f"-> Groq API #{key_index + 1} SUCCESS")
            state.current_groq_key = (state.current_groq_key + 1) % total_keys
            return result.strip()

        except Exception as e:
            error = str(e)
            print(f"!! Groq API #{key_index + 1} FAILED: {error}")
            state.current_groq_key = (state.current_groq_key + 1) % total_keys

            if "429" in error or "rate_limit" in error.lower():
                print(f"!! API #{key_index + 1} RATE LIMITED")
                continue
            continue

    print("!! ALL GROQ KEYS FAILED")
    return None


def generate_with_groq_compound(prompt, max_tokens=5000):
    """Web-research / SEO intelligence agent (rotates over NEWS_GROQ_KEYS)."""
    if not NEWS_GROQ_KEYS:
        return None
    total = len(NEWS_GROQ_KEYS)
    for _ in range(total):
        key_index = state.current_groq_key
        api_key = NEWS_GROQ_KEYS[key_index]
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
                    {"role": "user", "content": prompt},
                ],
                compound_custom={
                    "tools": {"enabled_tools": ["web_search", "visit_website"]}
                },
                temperature=0.15,
                max_tokens=max_tokens,
            )
            result = response.choices[0].message.content
            state.current_groq_key = (state.current_groq_key + 1) % total
            return result.strip() if result else None
        except Exception as e:
            print(f"!! Compound SEO research failed with key #{key_index + 1}: {e}")
            state.current_groq_key = (state.current_groq_key + 1) % total
    return None


def generate_with_groq_jobs(user_prompt):
    """Jobs robot model (rotates over JOB_GROQ_KEYS, groq/compound w/ web tools)."""
    if not JOB_GROQ_KEYS:
        print("!! NO GROQ API KEYS FOUND (jobs)")
        return None

    total_keys = len(JOB_GROQ_KEYS)

    for _ in range(total_keys):
        key_index = state.current_job_groq_key
        api_key = JOB_GROQ_KEYS[key_index]
        print(f"-> [JOBS] Using Groq API #{key_index + 1}/{total_keys}")

        try:
            client = Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=JOBS_GROQ_MODEL,
                messages=[
                    {"role": "system", "content": JOBS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                compound_custom={
                    "tools": {"enabled_tools": ["web_search", "visit_website"]}
                },
                temperature=0.2,
                max_tokens=4000,
            )

            result = response.choices[0].message.content
            if not result:
                raise Exception("Empty Groq response")

            print(f"-> [JOBS] Groq API #{key_index + 1} SUCCESS")
            state.current_job_groq_key = (state.current_job_groq_key + 1) % total_keys
            return result.strip()

        except Exception as e:
            error = str(e)
            print(f"!! [JOBS] Groq API #{key_index + 1} FAILED: {error}")
            state.current_job_groq_key = (state.current_job_groq_key + 1) % total_keys

            if "429" in error or "rate_limit" in error.lower():
                print(f"!! [JOBS] API #{key_index + 1} RATE LIMITED")
                continue
            continue

    print("!! [JOBS] ALL GROQ KEYS FAILED")
    return None
