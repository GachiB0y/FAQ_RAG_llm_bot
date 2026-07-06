import tiktoken

enc_old = tiktoken.get_encoding("cl100k_base")  # GPT-4/3.5, близко к Claude
enc_new = tiktoken.get_encoding("o200k_base")   # GPT-4o, новее и лучше для RU

samples = {
    "EN предложение": "The Federation reviews membership applications submitted through the personal account.",
    "RU предложение": "Федерация рассматривает заявки на вступление, поданные через личный кабинет на сайте.",
    "EN ~100 слов": " ".join(["The practical shooting federation establishes rules for membership and competition."] * 13),
    "RU ~100 слов": " ".join(["Федерация практической стрельбы устанавливает правила членства и проведения соревнований."] * 11),
}

print(f"{'Текст':<18}{'слов':>6}{'симв':>7}{'cl100k':>8}{'o200k':>7}{'tok/слово':>11}")
print("-" * 60)
for name, text in samples.items():
    w = len(text.split())
    c = len(text)
    to = len(enc_old.encode(text))
    tn = len(enc_new.encode(text))
    print(f"{name:<18}{w:>6}{c:>7}{to:>8}{tn:>7}{to / w:>11.2f}")

print("\nОтдельные слова (cl100k / o200k):")
for x in ["hello", "practical", "Федерация", "документ", "квалифицированного"]:
    print(f"  {x:<20}{len(enc_old.encode(x))} / {len(enc_new.encode(x))}")
