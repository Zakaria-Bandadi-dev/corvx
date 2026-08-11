from groq import Groq
from config.settings import JOB_GROQ_KEYS, JOBS_GROQ_MODEL

current_job_groq_key = 0

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

def generate_with_groq_jobs(user_prompt):
    global current_job_groq_key

    if not JOB_GROQ_KEYS:
        print("!! NO GROQ API KEYS FOUND (jobs)")
        return None

    total_keys = len(JOB_GROQ_KEYS)

    for attempt in range(total_keys):
        key_index = current_job_groq_key
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
            current_job_groq_key = (current_job_groq_key + 1) % total_keys
            return result.strip()

        except Exception as e:
            error = str(e)
            print(f"!! [JOBS] Groq API #{key_index + 1} FAILED: {error}")
            current_job_groq_key = (current_job_groq_key + 1) % total_keys

            if "429" in error or "rate_limit" in error.lower():
                print(f"!! [JOBS] API #{key_index + 1} RATE LIMITED")
                continue
            continue

    print("!! [JOBS] ALL GROQ KEYS FAILED")
    return None
