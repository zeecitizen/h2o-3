package water.fvec;

import com.google.common.base.Function;
import org.junit.*;
import water.MRTask;
import water.TestUtil;
import water.util.Functions;

import javax.annotation.Nullable;
import java.io.IOException;
import java.io.Serializable;
import java.util.HashSet;
import java.util.Set;



class Sine implements Function<Long, Double> {
  public Double apply(Long x) { return Math.sin(0.0001 * x); }
}

public class FunVecTest extends TestUtil {
  static Set<Vec> registry = new HashSet<>();

  @BeforeClass static public void setup() {  stall_till_cloudsize(1); }
  @Before public void clean() {
    registry.clear();
  }
  @After public void killem() {
    for (Vec v : registry) v.remove();
  }

  Vec register(Vec v) { registry.add(v); return v; }

  static <T> Vec fill(long size, Function<Long, T> fun) throws IOException {
    Vec v = Vec.makeFromFunction(size, fun);
    registry.add(v);
    return v;
  }

  @Test public void testSineFunction() {
    try {
      Vec v = fill(1 << 20, new Sine());
      int random = 44444;
      Assert.assertEquals(Math.sin(random * 0.0001), v.at(random), 0.000001);
      Function<Double, Double> sq = new Function<Double, Double>() {
        public Double apply(Double x) { return x*x;}
      };
      Vec iv = new FunVec(sq, v);
      new MRTask() {
        @Override
        public void map(Chunk c) {
          for (int i = 0; i < c._len; ++i) {
            long index = c._start + i;
            double expected = Math.sin(0.0001 * index) * Math.sin(0.0001 * index);
            double x = c.atd(i);
            if (x != expected)
              throw new RuntimeException("moo @" + c._cidx + "/" + i + " x=" + x + "; expected=" + expected);
          }
        }
      }.doAll(iv);
      iv.remove();
    } catch(Exception x) {
      x.printStackTrace();
      Assert.fail("Oops, exception " + x);
    }
  }
/*
  @Test public void testFunctionOfTwoArgs() throws IOException {
      Vec sines   = fill(1 << 24, new Function<Long, Double>() {
        public Double apply(Long x) { return Math.sin(0.0001 * x); }
      });
      Vec cosines = fill(1 << 24, new Function<Long, Double>() {
        public Double apply(Long x) { return Math.cos(0.0001 * x); }
      });

      Function<Double[], Double> sq = new Function<Double[], Double>() {
        public Double apply(Double[] x) { return x[0]*x[0] + x[1]*x[1];}
      };

      Vec iv = register(new FunVec(sq, sines, cosines));

      new MRTask() {
        @Override public void map(Chunk c) {
          for (int i = 0; i < c._len; ++i) {
            double x = c.atd(i);
            if (Math.abs(x - 1.0) > 0.0001) throw new RuntimeException("moo @" + c._cidx + "/" + i + " x=" + x + "; expected=1.0");
          }
        }
      }.doAll(iv);
  }


  @Test public void testFunction2() throws IOException {
    final Vec sines   = fill(1 << 24, new Function<Long, Double>() {
      public Double apply(Long x) { return Math.sin(0.0001 * x); }
    });
    final Vec cosines = fill(1 << 24, new Function<Long, Double>() {
      public Double apply(Long x) { return Math.cos(0.0001 * x); }
    });
    final Vec names = fill(1 << 24, new Function<Long, String>() {
      public String apply(Long x) { return "@" + x + ": "; }
    });

    final Functions.Function3<Double, String, Double, String> f3 = new Functions.Function3<Double, String, Double, String>() {
      public String apply(Double x, String txt, Double y) {
        double diff = Math.abs(x*x+y*y - 1.0);

        return txt + diff + " :)";
    };

    Vec iv = register(new FunVec(f3, sines, cosines, names));

    new MRTask() {
      @Override public void map(Chunk c) {
        for (int i = 0; i < c._len; ++i) {
          double x = c.atd(i);
          if (Math.abs(x - 1.0) > 0.0001) throw new RuntimeException("moo @" + c._cidx + "/" + i + " x=" + x + "; expected=1.0");
        }
      }
    }.doAll(iv);
  }
*/
}
