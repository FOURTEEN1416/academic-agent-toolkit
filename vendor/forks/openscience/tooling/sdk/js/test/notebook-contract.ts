import type { OpenScienceClient } from "../src/v2/client.js"
import type {
  NotebookExecuteData,
  NotebookInterruptData,
  NotebookKernelDeleteData,
  NotebookKernelInterruptData,
  NotebookKernelRestartData,
  NotebookKernelStopData,
  NotebookRestartData,
  NotebookStatusData,
  NotebookStopData,
} from "../src/v2/gen/types.gen.js"

type Assert<T extends true> = T
type Owner<T> = NonNullable<T> extends { sessionID: string } ? true : false
type Field<T, K extends PropertyKey> = K extends keyof NonNullable<T> ? true : false

type _executeOwner = Assert<Owner<NotebookExecuteData["body"]>>
type _statusOwner = Assert<Owner<NotebookStatusData["query"]>>
type _restartOwner = Assert<Owner<NotebookRestartData["body"]>>
type _stopOwner = Assert<Owner<NotebookStopData["body"]>>
type _interruptOwner = Assert<Owner<NotebookInterruptData["body"]>>
type _kernelRestartOwner = Assert<Owner<NotebookKernelRestartData["body"]>>
type _kernelStopOwner = Assert<Owner<NotebookKernelStopData["body"]>>
type _kernelInterruptOwner = Assert<Owner<NotebookKernelInterruptData["body"]>>
type _kernelDeleteOwner = Assert<Owner<NotebookKernelDeleteData["query"]>>

type Notebook = OpenScienceClient["notebook"]
type _executeMethodOwner = Assert<Field<Parameters<Notebook["execute"]>[0], "sessionID">>
type _statusMethodOwner = Assert<Field<Parameters<Notebook["status"]>[0], "sessionID">>
type _restartMethodOwner = Assert<Field<Parameters<Notebook["restart"]>[0], "sessionID">>
type _stopMethodOwner = Assert<Field<Parameters<Notebook["stop"]>[0], "sessionID">>
type _interruptMethodOwner = Assert<Field<Parameters<Notebook["interrupt"]>[0], "sessionID">>
type _kernelRestart = Assert<Field<Notebook["kernel"], "restart">>
type _kernelStop = Assert<Field<Notebook["kernel"], "stop">>
type _kernelInterrupt = Assert<Field<Notebook["kernel"], "interrupt">>
type _kernelDelete = Assert<Field<Notebook["kernel"], "delete">>

export const notebookContract = {
  execute: true as _executeOwner & _executeMethodOwner,
  status: true as _statusOwner & _statusMethodOwner,
  restart: true as _restartOwner & _restartMethodOwner,
  stop: true as _stopOwner & _stopMethodOwner,
  interrupt: true as _interruptOwner & _interruptMethodOwner,
  kernelRestart: true as _kernelRestartOwner & _kernelRestart,
  kernelStop: true as _kernelStopOwner & _kernelStop,
  kernelInterrupt: true as _kernelInterruptOwner & _kernelInterrupt,
  kernelDelete: true as _kernelDeleteOwner & _kernelDelete,
} as const
