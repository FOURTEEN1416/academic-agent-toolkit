import { createContext, createSignal, useContext, type Accessor, type JSX, type ParentProps } from "solid-js"
import { Portal, Show } from "solid-js/web"

/**
 * The file view owns one thin header line: the file's name and kind on the
 * left, its actions on the right, and between them a slot the active viewer
 * fills with its own controls (a PDF's pager and zoom, a table's row count).
 * Viewers rendered outside a file view (an artifact card, a message) have no
 * slot and keep their controls where they always were.
 */
type FileChrome = {
  slot: Accessor<HTMLElement | undefined>
  setSlot: (element: HTMLElement | undefined) => void
}

const Context = createContext<FileChrome>()

export function FileChromeProvider(props: ParentProps) {
  const [slot, setSlot] = createSignal<HTMLElement | undefined>()
  return <Context.Provider value={{ slot, setSlot }}>{props.children}</Context.Provider>
}

export function useFileChrome() {
  return useContext(Context)
}

/** Renders a viewer's controls in the file header when there is one, and in
 * place otherwise. `fallback` wraps the in-place rendering (the viewer's own
 * toolbar row); it is skipped entirely when the header takes the controls. */
export function ViewerControls(props: { children: JSX.Element; fallback?: (children: JSX.Element) => JSX.Element }) {
  const chrome = useFileChrome()
  const mount = () => chrome?.slot()
  return (
    <Show when={mount()} fallback={props.fallback ? props.fallback(props.children) : props.children}>
      {(element) => <Portal mount={element()}>{props.children}</Portal>}
    </Show>
  )
}
