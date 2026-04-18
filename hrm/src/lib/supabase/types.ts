export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type Database = {
	public: {
		Tables: {
			departments: {
				Row: {
					id: string;
					name: string;
					created_at: string;
				};
				Insert: {
					id?: string;
					name: string;
					created_at?: string;
				};
				Update: {
					id?: string;
					name?: string;
					created_at?: string;
				};
			};
			employees: {
				Row: {
					id: string;
					full_name: string;
					email: string;
					department_id: string | null;
					role: 'admin' | 'employee';
					status: 'active' | 'inactive';
					created_at: string;
				};
				Insert: {
					id?: string;
					full_name: string;
					email: string;
					department_id?: string | null;
					role?: 'admin' | 'employee';
					status?: 'active' | 'inactive';
					created_at?: string;
				};
				Update: {
					id?: string;
					full_name?: string;
					email?: string;
					department_id?: string | null;
					role?: 'admin' | 'employee';
					status?: 'active' | 'inactive';
					created_at?: string;
				};
			};
			leave_requests: {
				Row: {
					id: string;
					employee_id: string;
					start_date: string;
					end_date: string;
					total_days: number;
					reason: string;
					status: 'pending' | 'approved' | 'rejected';
					created_at: string;
				};
				Insert: {
					id?: string;
					employee_id: string;
					start_date: string;
					end_date: string;
					total_days: number;
					reason: string;
					status?: 'pending' | 'approved' | 'rejected';
					created_at?: string;
				};
				Update: {
					id?: string;
					employee_id?: string;
					start_date?: string;
					end_date?: string;
					total_days?: number;
					reason?: string;
					status?: 'pending' | 'approved' | 'rejected';
					created_at?: string;
				};
			};
		};
	};
};
