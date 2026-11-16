import { createEffect, createResource, For, onCleanup, Show } from "solid-js"
import { createStore } from "solid-js/store"
import { useData } from "../context/data"
import { Button } from "./button"

/** The action receipt stays immutable; this panel explicitly reads current job state. */
export function ComputeJobDetails(props: { id: string }) {
  const data = useData()
  const [view, setView] = createStore({ open: false })
  const [current, { refetch }] = createResource(
    () => (view.open && data.loadComputeJob ? props.id : false),
    async (id) =>
      data.loadComputeJob!(id).then(
        (job) => ({ job, error: undefined }),
        () => ({ job: undefined, error: "Current job status could not be read." }),
      ),
    // Keep loading and refresh states local to this panel, not the chat route.
    { initialValue: { job: undefined, error: undefined } },
  )
  createEffect(() => {
    const job = current.latest.job
    if (!view.open || !job) return
    const pending =
      ["queued", "running"].includes(job.status) ||
      job.lifecycle?.delivery === "pending" ||
      ["starting", "active", "unknown"].includes(job.lifecycle?.resource ?? "")
    if (!pending) return
    const timer = setInterval(() => {
      if (!document.hidden && !current.loading) void refetch()
    }, 2_500)
    onCleanup(() => clearInterval(timer))
  })
  return (
    <Show when={data.loadComputeJob}>
      <Button size="small" variant="ghost" aria-expanded={view.open} onClick={() => setView("open", !view.open)}>
        {view.open ? "Hide current job" : "View current job"}
      </Button>
      <Show when={view.open}>
        <div data-component="compute-job-details" aria-busy={current.loading}>
          <Show when={!current.loading || current.latest.job} fallback={<p>Reading current job…</p>}>
            <Show
              when={current.latest.job}
              fallback={
                <p>
                  {current.latest.error ?? "This job is no longer available. The action receipt is retained below."}
                </p>
              }
            >
              {(job) => (
                <>
                  <p>
                    <strong>Current status: {job().status}</strong> · {job().id}
                  </p>
                  <Show when={job().lifecycle}>
                    {(state) => (
                      <p>
                        Output: {state().delivery} · Resource: {state().resource}
                      </p>
                    )}
                  </Show>
                  <Show when={job().completed_at}>{(time) => <p>Finished {new Date(time()).toLocaleString()}</p>}</Show>
                  <Show when={job().exit_code !== undefined && job().exit_code !== null}>
                    <p>Exit code: {job().exit_code}</p>
                  </Show>
                  <For each={[job().error, job().capture_error, job().cleanup_error].filter(Boolean)}>
                    {(error) => <p>{error}</p>}
                  </For>
                  <For each={job().artifacts ?? []}>
                    {(artifact) => (
                      <Button
                        size="small"
                        variant="ghost"
                        onClick={() =>
                          artifact.artifact_id
                            ? data.openArtifact?.(artifact.artifact_id)
                            : data.openFile?.(artifact.path)
                        }
                      >
                        {artifact.path}
                      </Button>
                    )}
                  </For>
                </>
              )}
            </Show>
          </Show>
          <Button size="small" variant="ghost" disabled={current.loading} onClick={() => void refetch()}>
            Refresh current status
          </Button>
        </div>
      </Show>
    </Show>
  )
}
