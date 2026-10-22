package stateforecast

import java.io.{FileInputStream, ObjectInputStream, PrintWriter}
import fsm.SDFAInterface
import stream.GenericEvent
import play.api.libs.json.Json

/** Export only the experiment's type-only DSFA, never a generic predicate model. */
object ExportDFA {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "serialized DFA, output JSON")
    val in = new ObjectInputStream(new FileInputStream(args(0)))
    val fsms = try in.readObject().asInstanceOf[List[SDFAInterface]] finally in.close()
    require(fsms.size == 1)
    val fsm = fsms.head
    require(fsm.getRuntimeWindow == 0)
    val alphabet = List("LoadStart", "LoadEnd", "Gap")
    val transitions = fsm.getStates.toList.sorted.map { q =>
      q.toString -> Json.toJson(alphabet.map { symbol =>
        val next = fsm.getNextState(q, GenericEvent(symbol, 1L), null, null)
        require(next.size == 1)
        symbol -> next.head.stateId
      }.toMap)
    }.toMap
    val payload = Json.obj("scope" -> "type-only-dsfa-no-window", "start" -> fsm.getStartId,
      "finals" -> fsm.getFinals.toList.sorted, "alphabet" -> alphabet,
      "transitions" -> Json.toJson(transitions))
    val out = new PrintWriter(args(1))
    try out.println(Json.prettyPrint(payload)) finally out.close()
  }
}
