import csv, re, json, os

# ── helpers ──────────────────────────────────────────────────────────────────

def clean_isbn(raw):
    return re.sub(r'[=\"]', '', raw).strip()

def clean_review(raw):
    if not raw.strip():
        return ''
    text = re.sub(r'(<br\s*/?>\s*){2,}', '\n\n', raw)
    text = re.sub(r'<br\s*/?>', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'#\w+', '', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    paragraphs = text.split('\n\n')
    paragraphs = [re.sub(r'\s+', ' ', p).strip() for p in paragraphs]
    paragraphs = [p for p in paragraphs if p]
    return '\n\n'.join(paragraphs)

def extract_quotes(books):
    bad = [
        "read by the beach", "the worst hostages ever", "Grave of the Fireflies",
        "the generation of the ashes", "No love left", "At eighty, Ma had turned selfish",
        "so what would you have done", "10 days after the war", "One can find time",
        "The fact of being alive", "Words are the only victors", "I believe I have many feelings",
        "In a hole in the ground", "It's awful being a child",
        "You got cats at home", "Because ultimately only the witness",
        "There is no fire in hell", "reflections, impressions",
    ]
    patterns = [
        re.compile(r'\u201c(.*?)\u201d', re.DOTALL),
        re.compile(r'\u00ab(.*?)\u00bb', re.DOTALL),
        re.compile(r'"(.*?)"', re.DOTALL),
    ]
    quotes = []
    seen = set()
    for book in books:
        review = book.get('review', '')
        if not review:
            continue
        for pattern in patterns:
            for q in pattern.findall(review):
                q = q.strip()
                if not (25 < len(q) < 320):
                    continue
                if any(b.lower() in q.lower() for b in bad):
                    continue
                key = q[:40]
                if key in seen:
                    continue
                seen.add(key)
                quotes.append({
                    'quote': q,
                    'title': book['title'],
                    'author': book['author'],
                    'rating': book['rating'],
                })
    return quotes

# ── load overrides ────────────────────────────────────────────────────────────

with open('cover_overrides.json') as f:
    cover_overrides = json.load(f)

with open('genre_map.json') as f:
    genre_map = json.load(f)

# ── find CSV ──────────────────────────────────────────────────────────────────

csv_file = None
for fname in os.listdir('.'):
    if fname.startswith('goodreads') and fname.endswith('.csv'):
        csv_file = fname
        break

if not csv_file:
    raise FileNotFoundError("No goodreads CSV found in repo root")

print(f"Using: {csv_file}")

# ── process CSV ───────────────────────────────────────────────────────────────

with open(csv_file, encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

books = []
for r in rows:
    if r['Exclusive Shelf'] == 'to-read':
        continue  # skip wishlist
    bid = r['Book Id']
    isbn13 = clean_isbn(r['ISBN13'])
    isbn   = clean_isbn(r['ISBN'])

    # Cover: use override if exists, else derive from ISBN
    if bid in cover_overrides:
        cover = cover_overrides[bid]
    elif isbn13:
        cover = f'https://covers.openlibrary.org/b/isbn/{isbn13}-L.jpg'
    elif isbn:
        cover = f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg'
    else:
        cover = ''

    books.append({
        'id':        bid,
        'title':     r['Title'],
        'author':    r['Author'],
        'rating':    int(float(r['My Rating'])),
        'pages':     r['Number of Pages'],
        'year':      r['Original Publication Year'].split('.')[0] if r['Original Publication Year'] else '',
        'shelf':     r['Exclusive Shelf'],
        'date_read': r['Date Read'],
        'review':    clean_review(r['My Review']),
        'cover':     cover,
        'publisher': r['Publisher'],
        'genres':    genre_map.get(bid, ['Other']),
    })

print(f"Books: {len(books)} | Reviews: {sum(1 for b in books if b['review'])}")

quotes = extract_quotes(books)
print(f"Quotes: {len(quotes)}")

# ── inject into template ──────────────────────────────────────────────────────

books_json  = json.dumps(books,  ensure_ascii=True).replace('</script>', '<\\/script>')
quotes_json = json.dumps(quotes, ensure_ascii=True).replace('</script>', '<\\/script>')

with open('template.html') as f:
    template = f.read()

html = template.replace(
    'BOOKS_DATA_BLOCK',
    f'<script type="application/json" id="books-data">{books_json}</script>'
)
html = html.replace(
    'QUOTES_DATA_BLOCK',
    f'<script type="application/json" id="quotes-data">{quotes_json}</script>'
)

with open('index.html', 'w') as f:
    f.write(html)

print(f"index.html written — {len(html)//1024}KB")
