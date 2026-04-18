import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';
import { createBrowserClient } from '@supabase/ssr';
import type { SupabaseClient } from '@supabase/supabase-js';

import type { Database } from './types';

let browserClient: SupabaseClient<Database> | null = null;

export function getSupabaseBrowserClient() {
	if (!browser) {
		return null;
	}

	if (!env.PUBLIC_SUPABASE_URL || !env.PUBLIC_SUPABASE_PUBLISHABLE_KEY) {
		return null;
	}

	if (!browserClient) {
		browserClient = createBrowserClient<Database>(
			env.PUBLIC_SUPABASE_URL,
			env.PUBLIC_SUPABASE_PUBLISHABLE_KEY
		);
	}

	return browserClient;
}
