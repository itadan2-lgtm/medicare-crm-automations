import type { Task, TaskStatus } from '@/lib/api';

const STATUS_STYLES: Record<TaskStatus, string> = {
  pending: 'bg-slate-100 text-slate-700',
  claimed: 'bg-slate-200 text-slate-800',
  working: 'bg-blue-100 text-blue-800',
  done: 'bg-green-100 text-green-800',
  error: 'bg-red-100 text-red-800',
  awaiting_approval: 'bg-amber-100 text-amber-900',
  blocked: 'bg-red-200 text-red-900',
  cancelled: 'bg-slate-100 text-slate-500',
};

export function StatusBadge({ status }: { status: TaskStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}
    >
      {status.replace(/_/g, ' ')}
    </span>
  );
}

interface TaskListProps {
  tasks: Task[];
  onApprove?: (taskId: number) => void;
  onReject?: (taskId: number) => void;
}

export function TaskList({ tasks, onApprove, onReject }: TaskListProps) {
  if (tasks.length === 0) {
    return <p className="py-8 text-center text-sm text-slate-500">No tasks yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Task</th>
            <th className="px-3 py-2">Agent</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Depends on</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tasks.map((task) => (
            <tr key={task.task_id} className="align-top">
              <td className="px-3 py-2 text-slate-400">{task.task_id}</td>
              <td className="px-3 py-2 font-medium text-slate-800">
                {task.task_type}
                {task.error && (
                  // Agent-produced text rendered as text, never as HTML.
                  <p className="mt-1 max-w-md text-xs font-normal text-red-600">{task.error}</p>
                )}
              </td>
              <td className="px-3 py-2 text-slate-600">{task.assigned_to}</td>
              <td className="px-3 py-2">
                <StatusBadge status={task.status} />
              </td>
              <td className="px-3 py-2 text-slate-400">
                {task.depends_on.length ? task.depends_on.join(', ') : '—'}
              </td>
              <td className="px-3 py-2 text-right whitespace-nowrap">
                {task.status === 'awaiting_approval' && onApprove && onReject && (
                  <>
                    <button
                      onClick={() => onApprove(task.task_id)}
                      className="rounded bg-green-600 px-3 py-1 text-xs font-medium text-white hover:bg-green-700"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => onReject(task.task_id)}
                      className="ml-2 rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Reject
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
