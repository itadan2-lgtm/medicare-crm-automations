import { useRouter } from 'next/router';
import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { TaskList } from '@/components/TaskList';
import { api, type Project, type Task } from '@/lib/api';

export default function ProjectDetail() {
  const router = useRouter();
  const projectId = Number(router.query.id);

  const [project, setProject] = useState<Project | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!projectId || Number.isNaN(projectId)) return;
    try {
      const [projectData, taskData] = await Promise.all([
        api.getProject(projectId),
        api.projectTasks(projectId),
      ]);
      setProject(projectData);
      setTasks(taskData);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load project');
    }
  }, [projectId]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5_000);
    return () => clearInterval(timer);
  }, [load]);

  async function handleApprove(taskId: number) {
    await api.approveTask(taskId);
    await load();
  }

  async function handleReject(taskId: number) {
    await api.rejectTask(taskId);
    await load();
  }

  const counts = tasks.reduce<Record<string, number>>((acc, task) => {
    acc[task.status] = (acc[task.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <Link href="/" className="text-sm text-slate-500 hover:text-slate-700">
        ← All projects
      </Link>

      {error && (
        <div className="mt-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {project && (
        <header className="mb-6 mt-4">
          <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
          <p className="mt-1 text-sm text-slate-600">{project.goal}</p>
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            {Object.entries(counts).map(([status, count]) => (
              <span key={status}>
                {count} {status.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </header>
      )}

      <section className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 font-semibold text-slate-900">Tasks</h2>
        <TaskList tasks={tasks} onApprove={handleApprove} onReject={handleReject} />
      </section>
    </main>
  );
}
