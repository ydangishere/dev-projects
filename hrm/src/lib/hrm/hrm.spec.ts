import { describe, expect, it } from 'vitest';

import {
	buildDashboardSummary,
	canManageEmployees,
	getVisibleEmployees,
	getVisibleLeaveRequests
} from './hrm';
import type { Employee, LeaveRequest } from './types';

const employees: Employee[] = [
	{
		id: 'emp-1',
		fullName: 'Alex Nguyen',
		email: 'alex@acme.test',
		department: 'Engineering',
		role: 'admin',
		status: 'active'
	},
	{
		id: 'emp-2',
		fullName: 'Mia Tran',
		email: 'mia@acme.test',
		department: 'People',
		role: 'employee',
		status: 'active'
	},
	{
		id: 'emp-3',
		fullName: 'Liam Pham',
		email: 'liam@acme.test',
		department: 'Design',
		role: 'employee',
		status: 'inactive'
	}
];

const leaveRequests: LeaveRequest[] = [
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
		startDate: '2026-04-10',
		endDate: '2026-04-12',
		totalDays: 3,
		reason: 'Medical leave',
		status: 'approved'
	}
];

describe('hrm helpers', () => {
	it('builds summary cards from employees and leave requests', () => {
		expect(buildDashboardSummary(employees, leaveRequests)).toEqual({
			totalEmployees: 3,
			activeEmployees: 2,
			pendingLeaveRequests: 1,
			approvedLeaveDays: 3
		});
	});

	it('lets admin manage employees but blocks normal employees', () => {
		expect(canManageEmployees('admin')).toBe(true);
		expect(canManageEmployees('employee')).toBe(false);
	});

	it('shows all employees to admin', () => {
		expect(getVisibleEmployees('emp-1', 'admin', employees)).toHaveLength(3);
	});

	it('shows only the signed-in employee to non-admin users', () => {
		expect(getVisibleEmployees('emp-2', 'employee', employees)).toEqual([employees[1]]);
	});

	it('shows all leave requests to admin and personal requests to employee', () => {
		expect(getVisibleLeaveRequests('emp-1', 'admin', leaveRequests)).toHaveLength(2);
		expect(getVisibleLeaveRequests('emp-2', 'employee', leaveRequests)).toEqual([
			leaveRequests[0]
		]);
	});
});
