package water;

import jsr166y.CountedCompleter;
import jsr166y.RecursiveAction;

import java.util.concurrent.CancellationException;
import java.util.concurrent.PriorityBlockingQueue;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;


/**
 * Created by tomas on 11/5/16.
 *
 * Generic lightewight Local MRTask utility. Will launch requested number of tasks (on local node!), organized in a binary tree fashion, similar to MRTask.
 * Will attempt to share local results (MrFun instances) if the previous task has completed before launching current task.
 *
 * User expected to pass in MrFun implementing map(id), reduce(MrFun) and makeCopy() functions.
 * At the end of the task, MrFun holds the result.
 */
public class LocalMR<T extends MrFun<T>> extends H2O.H2OCountedCompleter<LocalMR>  {
  private int _lo;
  private int _hi;
  MrFun _mrFun;
  volatile Throwable _t;
  private  volatile boolean  _cancelled;

  private LocalMR<T> _root;
  private LocalMR _next; // for priority Q purpose, contains ref to the next task on the same priority level

  /**
   * Poor man's non-blocking priority for Forkjoin. Has fixed number of priority levels, non-blocking linked list per level.
   * Polling means walking the priorities in increasing order and grabbing the first task we can find.
   * Does not guarantee taking the lowest priority task in case other thread inserts lower priority during the polling (but then it's a race anyways).
   *
   * The motivation for this is as follows:
   * We have n tasks which can run in parallel, each task can be further split into m pieces which we would like to exploit to achieve maximum cpu utilization.
   * However, in MrT context, running each of the tasks in parallel carries memory overhead per task as we need private copy of the result for each active thread.
   * We want to do teh following:
         Run the n tasks in parallel and then parallelize within each task until we saturate the cpu.
   *     To minimize the memory overhead, we want to paralellize over primarily, only paralellize over m if there are cores to spare.
   *
   * I did not figure out how to do that in forkjoin without resorting to this.
   * Instead of forking we insert into the priority queue and fork a task which will poll and execute task from the q.
   */
  public static class TaskQ {
    private final AtomicReference<LocalMR>[] _taskQ = new AtomicReference[H2O.NUMCPUS];
    public TaskQ(){
      for(int i = 0; i < _taskQ.length; ++i)
        _taskQ[i] = new AtomicReference();
    }
    /**
     * Used instead of fork if we want prioritize some tasks over others.
     * @param t
     */
    public void submit(LocalMR t){
      add(t);
      // Instead of forking directly, fork a task which will poll the q.
      // One task forked for each submitted task -> guaranteed to complete.
      new RecursiveAction(){
        @Override
        protected void compute() {poll().compute2();}
      }.fork();
    }

    private  void add(LocalMR t){
      int p = t._lo;
      if(_taskQ.length <= p || p < 0)
        throw new IllegalArgumentException("Illegal priority level, allowed only values between 0 and NUMCPUS = " + H2O.NUMCPUS + ", got " + p);
      AtomicReference<LocalMR> ref = _taskQ[p];
      t._next = ref.get();
      while(!ref.compareAndSet(t._next,t)) t._next = ref.get();
    }

    private LocalMR poll(){
      while(true) // there is always a task in the q guaranteed
        for (int p = 0; p < _taskQ.length; ++p) {
          AtomicReference<LocalMR> ref = _taskQ[p];
          LocalMR t = ref.get();
          while (t != null && !ref.compareAndSet(t, t._next)) t = ref.get();
          if (t != null) {
            t._next = null;
            return t;
          }
        }
    }
  }
  private final TaskQ _taskQ;

  public LocalMR(MrFun mrt, int nthreads){this(mrt,nthreads,null,null);}
  public LocalMR(MrFun mrt, H2O.H2OCountedCompleter cc){this(mrt,H2O.NUMCPUS,null,cc);}
  public LocalMR(MrFun mrt, int nthreads, TaskQ taskQ, H2O.H2OCountedCompleter cc){
    super(cc);
    if(nthreads <= 0) throw new IllegalArgumentException("nthreads must be positive");
    _root = this;
    _mrFun = mrt; // used as golden copy and also will hold the result after task has finished.
    _lo = 0;
    _hi = nthreads;
    _prevTsk = null;
    _taskQ = taskQ;
  }
  private LocalMR(LocalMR src, LocalMR prevTsk,int lo, int hi) {
    super(src);
    _root = src._root;
    _prevTsk = prevTsk;
    _lo = lo;
    _hi = hi;
    _cancelled = src._cancelled;
    _taskQ = src._taskQ;
  }

  private LocalMR<T> _left;
  private LocalMR<T> _rite;
  private final LocalMR<T> _prevTsk; //will attempt to share MrFun with "previous task" if it's done by the time we start


  volatile boolean completed; // this task and all it's children completed
  volatile boolean started; // this task and all it's children completed
  public boolean isCancelRequested(){return _root._cancelled;}

  private int mid(){ return _lo + ((_hi - _lo) >> 1);}

  @Override
  public final void compute2() {
    started = true;
    if(_root._cancelled){
      tryComplete();
      return;
    }
    int mid = mid();
    assert _hi > _lo;
    if (_hi - _lo >= 2) {
      _left = new LocalMR(this, _prevTsk, _lo, mid);
      if (mid < _hi) {
        addToPendingCount(1);
        _rite = new LocalMR(this, _left, mid, _hi);
        if (_taskQ != null) _taskQ.submit(_rite);
        else _rite.fork();
      }
      _left.compute2();
    } else {
      if(_prevTsk != null && _prevTsk.completed){
        _mrFun = _prevTsk._mrFun;
        _prevTsk._mrFun = null;
      } else if(this != _root)
        _mrFun = _root._mrFun.makeCopy();
      try {
        _mrFun.map(mid);
      } catch (Throwable t) {
        t.printStackTrace();
        if (_root._t == null) {
          _root._t = t;
          _root._cancelled = true;
        }
      }
      tryComplete();
    }
  }

  @Override public boolean onExceptionalCompletion(Throwable ex, CountedCompleter cc){
    ex.printStackTrace();
    throw H2O.fail();
  }
  @Override
  public final void onCompletion(CountedCompleter cc) {
    try {
      if (_cancelled) {
        assert this == _root;
        completeExceptionally(_t == null ? new CancellationException() : _t); // instead of throw
        return;
      }
      if (_root._cancelled) return;
      if (_left != null && _left._mrFun != null && _mrFun != _left._mrFun) {
        assert _left.completed;
        if (_mrFun == null) _mrFun = _left._mrFun;
        else _mrFun.reduce(_left._mrFun);
      }
      if (_rite != null && _mrFun != _rite._mrFun) {
        assert _rite.completed;
        if (_mrFun == null) _mrFun = _rite._mrFun;
        else _mrFun.reduce(_rite._mrFun);
      }
      _left = null;
      _rite = null;
      completed = true;
    } catch(Throwable t){
      t.printStackTrace();
      throw H2O.fail(t.getMessage());
    }
  }
}
