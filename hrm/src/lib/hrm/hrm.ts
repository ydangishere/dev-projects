import type { DashboardSummary, Employee, LeaveRequest, UserRole } from './types';

export function buildDashboardSummary(
	employees: Employee[],
	leaveRequests: LeaveRequest[]
): DashboardSummary {
	return {
		totalEmployees: employees.length,
		activeEmployees: employees.filter((employee) => employee.status === 'active').length,
		pendingLeaveRequests: leaveRequests.filter((request) => request.status === 'pending').length,
		approvedLeaveDays: leaveRequests
			.filter((request) => request.status === 'approved')
			.reduce((total, request) => total + request.totalDays, 0)
	};
}

export function canManageEmployees(role: UserRole) {
	return role === 'admin';
}

export function getVisibleEmployees(
	viewerId: string,
	role: UserRole,
	employees: Employee[]
): Employee[] {
	if (role === 'admin') {
		return employees;
	}

	return employees.filter((employee) => employee.id === viewerId);
}

export function getVisibleLeaveRequests(
	viewerId: string,
	role: UserRole,
	leaveRequests: LeaveRequest[]
): LeaveRequest[] {
	if (role === 'admin') {
		return leaveRequests;
	}

	return leaveRequests.filter((request) => request.employeeId === viewerId);
}
