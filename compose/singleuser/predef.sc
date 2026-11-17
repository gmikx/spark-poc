import java.nio.file.{Files, Paths}
import scala.jdk.CollectionConverters._
Files.list(Paths.get("/opt/spark/jars")).iterator.asScala
  .filter(_.toString.endsWith(".jar")).foreach(p => interp.load.cp(os.Path(p)))
interp.configureCompiler(_.settings.nowarn.value = true)
@
import org.apache.spark.sql.SparkSession
lazy val spark: SparkSession = SparkSession.builder().getOrCreate()
lazy val sc = spark.sparkContext
