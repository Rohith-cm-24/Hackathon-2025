from supabase import create_client, Client

url: str = "https://opkacaoectvadkmdqidz.supabase.co"  
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9wa2FjYW9lY3R2YWRrbWRxaWR6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTg3ODUxNjgsImV4cCI6MjA3NDM2MTE2OH0.bTEYKdJs3L-0ogHRfVzNI-zOepEreLLc2SszM6hzDYo"       

# Initialize client
supabase: Client = create_client(url, key)

def get_policies():
    enabled_policies = supabase.table("policy").select("name,description").eq("is_enabled", True).execute()
    return enabled_policies.data



