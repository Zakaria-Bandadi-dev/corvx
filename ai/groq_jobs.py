from groq import Groq
from config.settings import JOB_GROQ_KEYS, JOBS_GROQ_MODEL

current_job_groq_key = 0

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
