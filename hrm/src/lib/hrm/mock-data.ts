import {
	buildDashboardSummary,
	getVisibleEmployees,
	getVisibleLeaveRequests
} from './hrm';
import type { Employee, LeaveRequest, UserRole } from './types';

export const departments = ['Engineering', 'People', 'Finance', 'Design'];

export const currentViewer = {
	id: 'emp-1',
	fullName: 'Alex Nguyen',
	role: 'admin' as UserRole
};

export const employees: Employee[] = [
	{
		id: 'emp-1',
		fullName: 'Alex Nguyen',
		email: 'alex@bardo-hrm.demo',
		department: 'Engineering',
		role: 'admin',
		status: 'active'
	},
	{
		id: 'emp-2',
		fullName: 'Mia Tran',
		email: 'mia@bardo-hrm.demo',
		department: 'People',
		role: 'employee',
		status: 'active'
	},
	{
		id: 'emp-3',
		fullName: 'Liam Pham',
		email: 'liam@bardo-hrm.demo',
		department: 'Design',
		role: 'employee',
		status: 'active'
	},
	{
		id: 'emp-4',
		fullName: 'Chloe Do',
		email: 'chloe@bardo-hrm.demo',
		department: 'Finance',
		role: 'employee',
		status: 'inactive'
	}
];

export const leaveRequests: LeaveRequest[] = [
	{
		id: 'leave-1',
		employeeId: 'emp-2',
		employeeName: 'Mia Tran',
		startDate: '2026-04-20',
		endDate: '2026-04-21',
		totalDays: 2,
		reason: 'Family event',
		status: 'pending'
	},
	{
		id: 'leave-2',
		employeeId: 'emp-3',
		employeeName: 'Liam Pham',
		startDate: '2026-04-22',
		endDate: '2026-04-24',
		totalDays: 3,
		reason: 'Annual leave',
		status: 'approved'
	},
	{
		id: 'leave-3',
		employeeId: 'emp-4',
		employeeName: 'Chloe Do',
		startDate: '2026-04-25',
		endDate: '2026-04-25',
		totalDays: 1,
		reason: 'Personal errand',
		status: 'rejected'
	}
];

export const dashboardSummary = buildDashboardSummary(employees, leaveRequests);
export const visibleEmployees = getVisibleEmployees(currentViewer.id, currentViewer.role, employees);
export const visibleLeaveRequests = getVisibleLeaveRequests(
	currentViewer.id,
	currentViewer.role,
	leaveRequests
);
