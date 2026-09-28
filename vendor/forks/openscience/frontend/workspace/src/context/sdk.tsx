import { createOpenScienceClient, type Event } from "@synsci/sdk/v2/client"
import { createSimpleContext } from "@synsci/ui/context"
import { createGlobalEmitter } from "@solid-primitives/event-bus"
import { createEffect, createMemo, onCleanup } from "solid-js"
import { useGlobalSDK } from "./global-sdk"
import { usePlatform } from "./platform"
import { createProjectRequest } from "@/utils/openscience-fetch"

export const { use: useSDK, provider: SDKProvider } = createSimpleContext({
  name: "SDK",
  init: (props: { directory: string; projectID?: string; scope?: string }) => {
    const platform = usePlatform()
    const globalSDK = useGlobalSDK()

    const directory = createMemo(() => props.directory)
    const projectID = createMemo(() => props.projectID)
    const scope = createMemo(() => props.scope ?? props.projectID ?? props.directory)
    const client = createMemo(() =>
      createOpenScienceClient({
        baseUrl: globalSDK.url,
        fetch: platform.fetch,
        directory: directory(),
        projectID: projectID(),
        throwOnError: true,
      }),
    )
    const request = createProjectRequest({
      baseUrl: () => globalSDK.url,
      fetch: () => platform.fetch ?? fetch,
      directory,
      projectID,
    })

    const emitter = createGlobalEmitter<{
      [key in Event["type"]]: Extract<Event, { type: key }>
    }>()

    createEffect(() => {
      const unsub = globalSDK.event.on(directory(), (event) => {
        emitter.emit(event.type, event)
      })
      onCleanup(unsub)
    })

    return {
      get directory() {
        return directory()
      },
      get projectID() {
        return projectID()
      },
      get scope() {
        return scope()
      },
      get client() {
        return client()
      },
      request,
      event: emitter,
      get url() {
        return globalSDK.url
      },
    }
  },
})
