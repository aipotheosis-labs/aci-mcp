SUPABASE_AUTH_SNIPPET = """
const getURL = () => {
  let url = process?.env?.NEXT_PUBLIC_VERCEL_URL || 'http://localhost:3000/'
  
  // Make sure to include `https://` when not localhost
  if (!url.startsWith('http')) {
    url = `https://${url}`
  }
  
  // Make sure to include a trailing `/`
  if (!url.endsWith('/')) {
    url = `${url}/`
  }
  
  return url
}

const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'github',
  options: {
    redirectTo: getURL(),
  },
})
"""
