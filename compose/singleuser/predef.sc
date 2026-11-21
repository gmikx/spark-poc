import java.nio.file.{Files, Paths}
import scala.jdk.CollectionConverters._
Files.list(Paths.get("/opt/spark/jars")).iterator.asScala
  .filter(_.toString.endsWith(".jar")).foreach(p => interp.load.cp(os.Path(p)))
interp.configureCompiler(_.settings.nowarn.value = true)
@
import org.apache.spark.sql.SparkSession
lazy val spark: SparkSession = SparkSession.builder().getOrCreate()
lazy val sc = spark.sparkContext

// Typowane Dataset z case class zdefiniowaną w komórce: Spark musi znać obiekt komórki (OuterScopes), inaczej NullPointerException.
// Hook dopisuje rejestrację na początku każdej komórki, która definiuje case class.
import almond.api.JupyterApi
kernel.addExecuteHook(new JupyterApi.ExecuteHook {
  def hook(code: String) =
    Right(if (code.contains("case class")) "org.apache.spark.sql.catalyst.encoders.OuterScopes.addOuterScope(this); " + code else code)
})
