import sqlite3
import os

conn = sqlite3.connect('data/newsletter.db')
c = conn.cursor()

# Fix article featured_image_local paths
c.execute('SELECT id, featured_image_local FROM articles WHERE featured_image_local IS NOT NULL')
rows = c.fetchall()
fixed = 0
for row in rows:
    old = row[1]
    # Convert 'backend\static\images\file.jpg' -> 'images/file.jpg'
    new = old.replace('\\', '/')
    new = new.replace('backend/static/', '')
    c.execute('UPDATE articles SET featured_image_local=? WHERE id=?', (new, row[0]))
    print(f'  Article {row[0]}: {old} -> {new}')
    fixed += 1

# Fix article_images local_path too
c.execute('SELECT id, local_path FROM article_images WHERE local_path IS NOT NULL')
rows = c.fetchall()
for row in rows:
    old = row[1]
    new = old.replace('\\', '/')
    new = new.replace('backend/static/', '')
    c.execute('UPDATE article_images SET local_path=? WHERE id=?', (new, row[0]))
    fixed += 1

conn.commit()
print(f'Fixed {fixed} image paths total')
conn.close()
