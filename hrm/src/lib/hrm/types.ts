export type UserRole = 'admin' | 'employee';
export type EmployeeStatus = 'active' | 'inactive';
export type LeaveStatus = 'pending' | 'approved' | 'rejected';

export type Employee = {
	id: string;
	fullName: string;
	email: string;
	department: string;
	role: UserRole;
	status: EmployeeStatus;
};

export type LeaveRequest = {
	id: string;
	employeeId: string;
	employeeName: string;
	startDate: string;
	endDate: string;
	totalDays: number;
	reason: string;
	status: LeaveStatus;
};

export type DashboardSummary = {
	totalEmployees: number;
	activeEmployees: number;
	pendingLeaveRequests: number;
	approvedLeaveDays: number;
};
