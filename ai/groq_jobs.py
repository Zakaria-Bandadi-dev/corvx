```python
from groq import Groq

from config.settings import (
    JOB_GROQ_KEYS,
    JOBS_GROQ_MODEL,
)


current_job_groq_key = 0


JOBS_SYSTEM_PROMPT = """You are a job-search assistant. Use web_search and visit_website to access the given site and find 5-10 latest real job offers currently available.

For each job, return Arabic only:
- title_ar: job title
- company_ar: company/institution
- description_ar: short task summary
- conditions_ar: requirements
- documents_ar: required documents
- how_to_apply_ar: exact application steps
- deadline: deadline or "غير محدد"
- source_url: direct job URL if available

Return ONLY a valid JSON array, no Markdown or explanation:

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

If no new jobs are found, return [].
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

        print(
            f"-> [JOBS] Using Groq API "
            f"#{key_index + 1}/{total_keys}"
        )

        try:
            client = Groq(api_key=api_key)

            response = client.chat.completions.create(
                model=JOBS_GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": JOBS_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
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
                temperature=0.2,

                # Reduced from 4000.
                # Enough for a JSON response containing 5-10 jobs.
                max_tokens=2500,
            )

            result = response.choices[0].message.content

            if not result:
                raise Exception("Empty Groq response")

            print(
                f"-> [JOBS] Groq API "
                f"#{key_index + 1} SUCCESS"
            )

            current_job_groq_key = (
                current_job_groq_key + 1
            ) % total_keys

            return result.strip()

        except Exception as e:
            error = str(e)

            print(
                f"!! [JOBS] Groq API "
                f"#{key_index + 1} FAILED: {error}"
            )

            current_job_groq_key = (
                current_job_groq_key + 1
            ) % total_keys

            if (
                "429" in error
                or "rate_limit" in error.lower()
            ):
                print(
                    f"!! [JOBS] API "
                    f"#{key_index + 1} RATE LIMITED"
                )
                continue

            continue

    print("!! [JOBS] ALL GROQ KEYS FAILED")

    return None
```
