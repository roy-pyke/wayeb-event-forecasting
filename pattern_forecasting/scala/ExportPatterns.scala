package patternforecast

import java.io.{FileInputStream, ObjectInputStream, PrintWriter}
import fsm.SDFAInterface
import stream.GenericEvent
import play.api.libs.json.Json

/** Exact author transitions for this finite type-only alphabet. */
object ExportPatterns {
  def main(args: Array[String]): Unit = {
    require(args.length == 3, "serialized FSM, output JSON, pattern names")
    val input = new ObjectInputStream(new FileInputStream(args(0)))
    val fsms = try input.readObject().asInstanceOf[List[SDFAInterface]] finally input.close()
    val names = args(2).split(",").toList
    require(fsms.size == names.size)
    val alphabet = List("A", "B", "C", "D")
    val tables = fsms.zip(names).map { case (fsm, name) =>
      require(fsm.getRuntimeWindow == 0)
      val transitions = fsm.getStates.toList.sorted.map { q =>
        q.toString -> Json.toJson(alphabet.map { symbol =>
          val next = fsm.getNextState(q, GenericEvent(symbol, 1L), null, null)
          require(next.size == 1)
          symbol -> next.head.stateId
        }.toMap)
      }.toMap
      name -> Json.obj("start" -> fsm.getStartId, "finals" -> fsm.getFinals.toList.sorted,
        "transitions" -> Json.toJson(transitions))
    }.toMap
    val output = new PrintWriter(args(1))
    try output.println(Json.prettyPrint(Json.obj("scope" -> "type-only-no-window",
      "alphabet" -> alphabet, "patterns" -> Json.toJson(tables)))) finally output.close()
  }
}
