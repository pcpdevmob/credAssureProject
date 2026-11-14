'use client';
import { PageHeader } from '@/components/PageHeader';
import AuditList from '@/components/AuditList';
export default function Audit() { return <><PageHeader title="Audit log" sub="Every agent decision, calculation, blocker, revision and approval — with timestamp and case ID (OBJ-06)" /><AuditList /></>; }
