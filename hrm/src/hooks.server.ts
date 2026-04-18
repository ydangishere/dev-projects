import type { Handle } from '@sveltejs/kit';

import { createSupabaseServerClient } from '$lib/supabase/server';

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.supabase = createSupabaseServerClient(event.cookies);

	event.locals.safeGetSession = async () => {
		if (!event.locals.supabase) {
			return { session: null, user: null };
		}

		const {
			data: { user }
		} = await event.locals.supabase.auth.getUser();
		const {
			data: { session }
		} = await event.locals.supabase.auth.getSession();

		return { session, user };
	};

	return resolve(event);
};
