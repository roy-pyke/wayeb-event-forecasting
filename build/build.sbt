// Deployment overlay: compile the pinned author sources without editing them.
import sbtassembly.AssemblyPlugin.autoImport._

ThisBuild / scalaVersion := "2.12.10"
ThisBuild / version := "0.1.0"
ThisBuild / organization := "research.wayeb.deployment"

val repositoryRoot = file("..").getCanonicalFile
val authorWayeb = repositoryRoot / "upstream" / "Wayeb" / "cef"
val adaptiveWayeb = repositoryRoot / "upstream" / "rtcef" / "libraries" / "models" / "wrappers" / "wayeb"

val authorDependencies = Seq(
  "org.scala-lang" % "scala-reflect" % "2.12.10",
  "org.scala-lang.modules" %% "scala-parser-combinators" % "1.1.2",
  "org.scala-lang.modules" %% "scala-xml" % "1.2.0",
  "ch.qos.logback" % "logback-classic" % "1.2.3",
  "com.typesafe.scala-logging" %% "scala-logging" % "3.9.2",
  "com.typesafe.slick" %% "slick" % "3.3.0",
  "com.typesafe.slick" %% "slick-hikaricp" % "3.3.0",
  "org.postgresql" % "postgresql" % "42.2.9",
  "com.github.tototoshi" %% "scala-csv" % "1.3.6",
  "org.scalanlp" %% "breeze" % "1.0",
  "org.scalanlp" %% "breeze-natives" % "1.0",
  "com.github.haifengl" %% "smile-scala" % "1.5.3",
  "org.locationtech.jts" % "jts-core" % "1.16.1",
  "com.github.scopt" %% "scopt" % "3.7.1",
  "com.typesafe" % "config" % "1.4.0",
  "de.learnlib" % "learnlib-rpni" % "0.15.0",
  "com.typesafe.play" %% "play-json" % "2.7.4",
  "junit" % "junit" % "4.13",
  "org.scalatest" %% "scalatest" % "3.0.8" % Test,
  "org.scalacheck" %% "scalacheck" % "1.14.1" % Test
)

def deploymentSettings(source: File, jarName: String) = Seq(
  Compile / scalaSource := source / "src" / "main" / "scala",
  Compile / resourceDirectory := source / "src" / "main" / "resources",
  Test / scalaSource := source / "src" / "test" / "scala",
  Test / resourceDirectory := source / "src" / "test" / "resources",
  libraryDependencies ++= authorDependencies,
  dependencyOverrides ++= Seq(
    "org.scala-lang" % "scala-compiler" % "2.12.10",
    "org.scala-lang" % "scala-library" % "2.12.10",
    "org.scala-lang" % "scala-reflect" % "2.12.10",
    "org.scala-lang.modules" %% "scala-parser-combinators" % "1.1.2",
    "org.scala-lang.modules" %% "scala-xml" % "1.2.0"
  ),
  Compile / mainClass := Some("ui.WayebCLI"),
  assembly / mainClass := Some("ui.WayebCLI"),
  assembly / assemblyJarName := jarName,
  assembly / assemblyOutputPath := repositoryRoot / "artifacts" / jarName,
  assembly / test := {},
  assembly / assemblyMergeStrategy := {
    case PathList("META-INF", _ @ _*) => MergeStrategy.discard
    case _ => MergeStrategy.first
  },
  Test / parallelExecution := false
)

lazy val core = project.in(file("core"))
  .settings(deploymentSettings(authorWayeb, "wayeb.jar"))
  .settings(libraryDependencies += "org.apache.flink" %% "flink-connector-kafka" % "1.9.0")

lazy val adaptive = project.in(file("adaptive"))
  .settings(deploymentSettings(adaptiveWayeb, "rtcef-wayeb.jar"))
  .settings(
    Compile / unmanagedJars += Attributed.blank(adaptiveWayeb / "lib" / "py4j0.10.9.2.jar"),
    libraryDependencies ++= Seq(
      "org.apache.kafka" % "kafka-clients" % "3.4.0",
      "org.apache.avro" % "avro" % "1.11.0",
      "com.storm-enroute" %% "scalameter-core" % "0.18",
      "com.github.vagmcs" %% "scalatikz" % "0.4.4"
    )
  )

// Research adapter only; uses the original core classes without changing them.
lazy val stateBridge = project.in(file("stateBridge"))
  .dependsOn(core)
  .settings(
    Compile / scalaSource := repositoryRoot / "state_forecasting" / "scala",
    Compile / mainClass := Some("stateforecast.ExportDFA"),
    Compile / run / fork := true,
    Compile / run / baseDirectory := repositoryRoot,
    publish / skip := true
  )
  .disablePlugins(AssemblyPlugin)

lazy val root = project.in(file("."))
  .aggregate(core, adaptive)
  .settings(publish / skip := true)
  .disablePlugins(AssemblyPlugin)

lazy val patternBridge = project.in(file("patternBridge"))
  .dependsOn(core)
  .settings(
    Compile / scalaSource := repositoryRoot / "pattern_forecasting" / "scala",
    Compile / mainClass := Some("patternforecast.ExportPatterns"),
    Compile / run / fork := true,
    Compile / run / baseDirectory := repositoryRoot,
    publish / skip := true
  )
  .disablePlugins(AssemblyPlugin)

