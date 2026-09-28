import { ManagedEnvironments } from "../../src/science/kernel/environment-manager"

if (process.argv[2] === "runtime") {
  await ManagedEnvironments.runtime("python")
  await ManagedEnvironments.runtime("python")
  console.log("runtime-ok")
} else if (process.argv[2] === "bootstrap") {
  await ManagedEnvironments.bootstrap()
  console.log("bootstrap-ok")
} else {
  throw new Error("Expected runtime or bootstrap mode")
}
