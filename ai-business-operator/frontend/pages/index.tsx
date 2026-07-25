import { useEffect, useState } from 'react';
import { ProjectCard } from '@/components/ProjectCard';
import { api, ApiError, type Project, type Task } from '@/lib/api';

export default function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [approvals, setApprovals] = useState<Task[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', goal: '', niche: '' });

  async function load() {
    try {
      const [projectList, approvalList] = await Promise.all([
        api.listProjects(),
        api.pendingApproval(),
      ]);
      setProjects(projectList);
      setApprovals(approvalList);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError('Session expired. Sign in again.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load');
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // Poll while tasks are in flight. TODO(phase-4): swap for a websocket or SSE
    // stream off the event bus, so the dashboard reflects state as it changes.
    const timer = setInterval(load, 10_000);
    return () => clearInterval(timer);
  }, []);

  async function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    try {
      await api.createProject({
        name: form.name,
        goal: form.goal,
        niche: form.niche || undefined,
      });
      setForm({ name: '', goal: '', niche: '' });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create project');
    } finally {
      setCreating(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">AI Business Operator</h1>
        <p className="mt-1 text-sm text-slate-600">
          Give it a goal. It researches, builds, and prepares the funnel — and stops for your
          approval before anything goes live.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {approvals.length > 0 && (
        <section className="mb-8 rounded-lg border border-amber-200 bg-amber-50 p-4">
          <h2 className="font-semibold text-amber-900">
            {approvals.length} task{approvals.length === 1 ? '' : 's'} waiting for you
          </h2>
          <p className="mt-1 text-sm text-amber-800">
            Publishing and payments never run without approval.
          </p>
          <ul className="mt-3 space-y-1 text-sm">
            {approvals.map((task) => (
              <li key={task.task_id}>
                <a
                  href={`/projects/${task.project_id}`}
                  className="text-amber-900 underline underline-offset-2"
                >
                  #{task.task_id} {task.task_type}
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mb-8 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 font-semibold text-slate-900">New project</h2>
        <form onSubmit={handleCreate} className="grid gap-3 sm:grid-cols-3">
          <input
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Project name"
            className="rounded border border-slate-300 px-3 py-2 text-sm"
          />
          <input
            required
            value={form.goal}
            onChange={(e) => setForm({ ...form, goal: e.target.value })}
            placeholder="Goal, e.g. launch a home-fitness ebook business"
            className="rounded border border-slate-300 px-3 py-2 text-sm sm:col-span-2"
          />
          <input
            value={form.niche}
            onChange={(e) => setForm({ ...form, niche: e.target.value })}
            placeholder="Niche (optional)"
            className="rounded border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={creating}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
          >
            {creating ? 'Planning…' : 'Create project'}
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-4 font-semibold text-slate-900">Projects</h2>
        {loading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : projects.length === 0 ? (
          <p className="text-sm text-slate-500">No projects yet. Create one above.</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {projects.map((project) => (
              <ProjectCard key={project.project_id} project={project} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
