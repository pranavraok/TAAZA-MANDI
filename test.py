from supabase import create_client

SUPABASE_URL = "https://wesrjuxmbudivggitawl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indlc3JqdXhtYnVkaXZnZ2l0YXdsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTU4NDA3OTYsImV4cCI6MjA3MTQxNjc5Nn0.KTHwj3jAGWC-9d5gIL6Znr2u22ycdpo1VXq8JHJq3Jg"


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

bucket = "products"
file_name = "test_upload.txt"

file_bytes = b"Hello Supabase!"

upload_res = supabase.storage.from_(bucket).upload(
    path=file_name,
    file=file_bytes,
    file_options={"content-type": "text/plain"}
)

print("UPLOAD RESULT:", upload_res)

url_res = supabase.storage.from_(bucket).get_public_url(file_name)
print("PUBLIC URL:", url_res["publicUrl"])