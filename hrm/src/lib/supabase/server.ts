import { env } from '$env/dynamic/public';
import { createServerClient } from '@supabase/ssr';
import type { Cookies } from '@sveltejs/kit';

import type { Database } from './types';

export function createSupabaseServerClient(cookies: Cookies) {
	if (!env.PUBLIC_SUPABASE_URL || !env.PUBLIC_SUPABASE_PUBLISHABLE_KEY) {
		return null;
	}

	return createServerClient<Database>(
		env.PUBLIC_SUPABASE_URL,
		env.PUBLIC_SUPABASE_PUBLISHABLE_KEY,
		{
			cookies: {
				getAll: () => cookies.getAll(),
				setAll: (cookiesToSet) => {
					cookiesToSet.forEach(({ name, value, options }) => {
						cookies.set(name, value, { ...options, path: '/' });
					});
				}
			}
		}
	);
}
