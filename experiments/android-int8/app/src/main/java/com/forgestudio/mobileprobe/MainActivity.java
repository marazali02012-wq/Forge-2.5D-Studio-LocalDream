package com.forgestudio.mobileprobe;

import android.app.*;
import android.os.*;
import android.content.*;
import android.graphics.*;
import android.net.Uri;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.JSONObject;

public class MainActivity extends Activity{
 private static final int MODEL=10, PHOTO=11, EXPORT=12, REPORT=13;
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private TextView status,details; private Button importModel,choosePhoto,run,export,report,front,side,back;
 private ImageView image; private ProgressBar progress; private File encoder,decoder,lastGlb,lastReport; private Uri photo;
 private Bitmap[] views; private boolean busy=false;
 private final String bg="#181D24", panel="#25303B", ink="#EBEDF2", accent="#E4B875";
 private int px(float dp){return (int)(dp*getResources().getDisplayMetrics().density+.5f);}
 private Button button(String label,LinearLayout parent,Runnable action){Button b=new Button(this);b.setText(label);b.setAllCaps(false);b.setTextColor(Color.parseColor(ink));b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.parseColor(panel)));b.setMinHeight(px(44));parent.addView(b,new LinearLayout.LayoutParams(-1,-2));b.setOnClickListener(v->action.run());return b;}
 @Override public void onCreate(Bundle state){super.onCreate(state);
  encoder=new File(getFilesDir(),"triposr-encoder-int8.onnx");decoder=new File(getFilesDir(),"triposr-decoder-fp32.onnx");
  lastGlb=new File(getFilesDir(),"forge-phone.glb");lastReport=new File(getFilesDir(),"forge-phone-report.json");
  ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(Color.parseColor(bg));
  LinearLayout body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);body.setPadding(px(16),px(12),px(16),px(16));scroll.addView(body);setContentView(scroll);
  if(Build.VERSION.SDK_INT>=35)scroll.setOnApplyWindowInsetsListener((v,i)->{android.graphics.Insets bars=i.getInsets(WindowInsets.Type.systemBars());v.setPadding(bars.left,bars.top,bars.right,bars.bottom);return i;});
  TextView title=new TextView(this);title.setText("FORGE 3D | Telefon RAM testi");title.setTextSize(20);title.setTextColor(Color.parseColor(accent));body.addView(title);
  details=new TextView(this);details.setTextSize(13);details.setTextColor(Color.parseColor(ink));body.addView(details);
  importModel=button("1 · 433 MB INT8 model dosyasını seç",body,()->pick(MODEL,"*/*"));
  choosePhoto=button("2 · Resim seç (isteğe bağlı)",body,()->pick(PHOTO,"image/*"));
  run=button("3 · Telefonda gerçek 3D üret",body,this::start);
  progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setIndeterminate(true);progress.setVisibility(View.GONE);body.addView(progress);
  status=new TextView(this);status.setTextSize(14);status.setTextColor(Color.parseColor(ink));status.setTextIsSelectable(true);status.setPadding(0,px(8),0,px(8));body.addView(status);
  image=new ImageView(this);image.setAdjustViewBounds(true);image.setScaleType(ImageView.ScaleType.FIT_CENTER);body.addView(image,new LinearLayout.LayoutParams(-1,px(220)));
  LinearLayout nav=new LinearLayout(this);nav.setOrientation(LinearLayout.HORIZONTAL);body.addView(nav);
  front=angle("Ön",nav,0);side=angle("Yan",nav,1);back=angle("Arka",nav,2);
  export=button("GLB kaydet",body,()->save(EXPORT,"forge-phone.glb"));report=button("RAM raporunu kaydet",body,()->save(REPORT,"forge-phone-report.json"));
  status.setText("İnternet izni yok. Modeli bir kez içe aktar. Resim seçmezsen paket içindeki robot kullanılacak.");
  refresh();
 }
 private Button angle(String s,LinearLayout row,int i){Button b=new Button(this);b.setAllCaps(false);b.setText(s);b.setTextColor(Color.parseColor(ink));b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.parseColor(panel)));row.addView(b,new LinearLayout.LayoutParams(0,px(44),1));b.setOnClickListener(v->{if(views!=null)image.setImageBitmap(views[i]);});return b;}
 private long availableMiB(){ActivityManager.MemoryInfo m=new ActivityManager.MemoryInfo();((ActivityManager)getSystemService(ACTIVITY_SERVICE)).getMemoryInfo(m);return m.availMem/1048576;}
 private void refresh(){boolean ready=encoder.length()==Engine.ENCODER_BYTES;details.setText("CPU ARM64 / x86_64 · 1 iş parçacığı · 64³\nModel: "+(ready?"dosya mevcut (SHA çalıştırırken doğrulanır)":"henüz seçilmedi")+"\nResim: "+(photo==null?"örnek robot":"seçilen resim")+"\nSistem boş RAM: "+availableMiB()+" MiB");
  importModel.setEnabled(!busy);choosePhoto.setEnabled(!busy);run.setEnabled(!busy&&ready);export.setEnabled(!busy&&lastGlb.isFile());report.setEnabled(!busy&&lastReport.isFile());front.setEnabled(!busy&&views!=null);side.setEnabled(!busy&&views!=null);back.setEnabled(!busy&&views!=null);progress.setVisibility(busy?View.VISIBLE:View.GONE);
  if(busy)getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
 }
 private void pick(int request,String mime){Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.setType(mime);i.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,request);}
 private void save(int request,String name){Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);i.setType(request==REPORT?"application/json":"application/octet-stream");i.addCategory(Intent.CATEGORY_OPENABLE);i.putExtra(Intent.EXTRA_TITLE,name);startActivityForResult(i,request);}
 private void log(String s){runOnUiThread(()->status.setText(s));}
 private void begin(){busy=true;refresh();}
 private void done(String s){runOnUiThread(()->{busy=false;status.setText(s);refresh();});}
 private void copy(InputStream in,OutputStream out)throws IOException{byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}
 @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null||data.getData()==null||busy)return;Uri uri=data.getData();
  if(request==PHOTO){photo=uri;status.setText("Resim seçildi. Şeffaf PNG veya sade arka plan kullan.");refresh();return;}
  if(request==MODEL){begin();worker.execute(()->{File temp=new File(getFilesDir(),"encoder.part");try{
    if(getFilesDir().getUsableSpace()<Engine.ENCODER_BYTES+64*1048576L)throw new IOException("En az 500 MB boş dahili alan gerekiyor.");
    log("Model yerel depoya kopyalanıyor...");
    try(InputStream in=getContentResolver().openInputStream(uri);OutputStream out=new FileOutputStream(temp)){if(in==null)throw new IOException("Dosya açılamadı");copy(in,out);}
    log("SHA-256 doğrulanıyor...");if(temp.length()!=Engine.ENCODER_BYTES||!Engine.sha(temp).equals(Engine.ENCODER_SHA))throw new IOException("Yanlış model veya eksik indirme");
    if(!temp.renameTo(encoder))throw new IOException("Model kaydedilemedi");done("Model doğrulandı. Artık internet olmadan çalıştırılabilir.");
   }catch(Exception e){done("Model alınamadı: "+e.getMessage());}finally{temp.delete();}});return;}
  if(request==EXPORT||request==REPORT){File f=request==EXPORT?lastGlb:lastReport;begin();worker.execute(()->{try(InputStream in=new FileInputStream(f);OutputStream out=getContentResolver().openOutputStream(uri,"w")){if(out==null)throw new IOException("Hedef açılamadı");copy(in,out);done("Dosya kaydedildi: "+f.getName());}catch(Exception e){done("Kaydetme hatası: "+e.getMessage());}});}
 }
 private void start(){if(busy)return;if(!android.os.Process.is64Bit()){status.setText("64 bit Android işlem gerekiyor.");return;}if(availableMiB()<1500){status.setText("Boş RAM 1500 MiB altında. Diğer uygulamaları kapatıp tekrar dene.");return;}
  begin();final Uri selected=photo;worker.execute(()->{try{
   if(!decoder.isFile()||!Engine.sha(decoder).equals(Engine.DECODER_SHA)){try(InputStream in=getAssets().open("triposr-decoder-fp32.onnx");OutputStream out=new FileOutputStream(decoder)){copy(in,out);}}
   JSONObject meta;try(InputStream in=getAssets().open("triposr-decoder-meta.json");ByteArrayOutputStream o=new ByteArrayOutputStream()){copy(in,o);meta=new JSONObject(o.toString("UTF-8")).getJSONObject("params");}
   Bitmap b=load(selected);float[] input=preprocess(b);b.recycle();
   Engine.Mesh m=Engine.run(encoder,decoder,input,(float)meta.getDouble("radius"),(float)meta.getDouble("density_threshold"),64,this::log);
   File tmp=new File(getFilesDir(),"forge-phone.tmp");Engine.saveGlb(m,tmp);if(!tmp.renameTo(lastGlb))throw new IOException("GLB kaydedilemedi");
   JSONObject j=new JSONObject();j.put("device",Build.MANUFACTURER+" "+Build.MODEL);j.put("android",Build.VERSION.RELEASE);j.put("abi",Build.SUPPORTED_ABIS[0]);j.put("vertices",m.v.size());j.put("triangles",m.f.size());j.put("elapsed_ms",m.elapsedMs);j.put("vmhwm_mib",m.hwmMiB);j.put("glb_bytes",lastGlb.length());j.put("grid",64);j.put("mode","raw-int8-cpu-one-thread");
   try(OutputStream out=new FileOutputStream(lastReport)){out.write(j.toString(2).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
   log("Gerçek 3D önizlemeler hazırlanıyor...");Bitmap[] next=new Bitmap[3];for(int i=0;i<3;i++)next[i]=preview(m,i);
   runOnUiThread(()->{if(views!=null)for(Bitmap old:views)old.recycle();views=next;image.setImageBitmap(views[0]);});
   done("ÜRETİM BAŞARILI\n"+m.f.size()+" üçgen · "+(m.elapsedMs/1000f)+" sn\nİşlem RAM tepe: "+m.hwmMiB+" MiB\nGLB ve RAM raporunu kaydedebilirsin.");
  }catch(Throwable e){done("Üretim başarısız: "+e.getClass().getSimpleName()+" · "+e.getMessage());}});}
 private Bitmap load(Uri uri)throws IOException{if(uri==null){try(InputStream in=getAssets().open("robot.png")){Bitmap b=BitmapFactory.decodeStream(in);if(b==null)throw new IOException("Örnek resim");return b;}}
  BitmapFactory.Options o=new BitmapFactory.Options();o.inJustDecodeBounds=true;try(InputStream in=getContentResolver().openInputStream(uri)){BitmapFactory.decodeStream(in,null,o);}
  if(o.outWidth<1||o.outHeight<1)throw new IOException("Resim biçimi desteklenmiyor");o.inSampleSize=1;while(Math.max(o.outWidth,o.outHeight)/o.inSampleSize>2048)o.inSampleSize*=2;o.inJustDecodeBounds=false;o.inPreferredConfig=Bitmap.Config.ARGB_8888;try(InputStream in=getContentResolver().openInputStream(uri)){Bitmap b=BitmapFactory.decodeStream(in,null,o);if(b==null)throw new IOException("Resim açılamadı");return b;}}
 static float[] preprocess(Bitmap b){int w=b.getWidth(),h=b.getHeight(),x0=w,y0=h,x1=-1,y1=-1;boolean alpha=false;int[] row=new int[w];
  for(int y=0;y<h;y++){b.getPixels(row,0,w,0,y,w,1);for(int x=0;x<w;x++){int a=Color.alpha(row[x]);if(a<255)alpha=true;if(a>0){x0=Math.min(x0,x);x1=Math.max(x1,x);y0=Math.min(y0,y);y1=Math.max(y1,y);}}}
  if(x1<x0)throw new IllegalArgumentException("Tamamen boş resim");
  Rect src=alpha?new Rect(x0,y0,x1+1,y1+1):new Rect(0,0,w,h);float scale=512f/Math.max(src.width(),src.height())*(alpha?.85f:1f);float dw=src.width()*scale,dh=src.height()*scale;
  Bitmap dst=Bitmap.createBitmap(512,512,Bitmap.Config.ARGB_8888);Canvas c=new Canvas(dst);c.drawColor(Color.rgb(128,128,128));Paint p=new Paint(Paint.FILTER_BITMAP_FLAG);c.drawBitmap(b,src,new RectF((512-dw)/2,(512-dh)/2,(512+dw)/2,(512+dh)/2),p);
  int[] pix=new int[512*512];dst.getPixels(pix,0,512,0,0,512,512);dst.recycle();float[] out=new float[pix.length*3];for(int i=0;i<pix.length;i++){out[i]=Color.red(pix[i])/255f;out[i+pix.length]=Color.green(pix[i])/255f;out[i+pix.length*2]=Color.blue(pix[i])/255f;}return out;
 }
 static Bitmap preview(Engine.Mesh m,int angle){int size=560;Bitmap b=Bitmap.createBitmap(size,size,Bitmap.Config.ARGB_8888);Canvas canvas=new Canvas(b);canvas.drawColor(Color.rgb(24,29,36));
  double yaw=angle*Math.PI/2,cs=Math.cos(yaw),sn=Math.sin(yaw);int nv=m.v.size();float[][] q=new float[nv][3];float[] lo={Float.MAX_VALUE,Float.MAX_VALUE},hi={-Float.MAX_VALUE,-Float.MAX_VALUE};
  for(int i=0;i<nv;i++){float[] v=m.v.get(i);q[i]=new float[]{(float)(v[0]*cs-v[2]*sn),v[1],(float)(v[0]*sn+v[2]*cs)};for(int j=0;j<2;j++){lo[j]=Math.min(lo[j],q[i][j]);hi[j]=Math.max(hi[j],q[i][j]);}}
  float sc=480/Math.max(hi[0]-lo[0],hi[1]-lo[1]),cx=(lo[0]+hi[0])/2,cy=(lo[1]+hi[1])/2;Integer[] order=new Integer[m.f.size()];for(int i=0;i<order.length;i++)order[i]=i;
  Arrays.sort(order,Comparator.comparingDouble(i->{int[] f=m.f.get(i);return q[f[0]][2]+q[f[1]][2]+q[f[2]][2];}));Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);Path path=new Path();
  for(int index:order){int[] f=m.f.get(index);float[] a=q[f[0]],d=q[f[1]],e=q[f[2]],n=Engine.cross(Engine.sub(d,a),Engine.sub(e,a));float l=(float)Math.sqrt(Engine.dot(n,n));if(l<1e-12f)continue;float light=.4f+.6f*Math.max(0,(n[0]*.3f+n[1]*.65f+n[2]*.69f)/l);int[] col=new int[3];for(int j=0;j<3;j++)col[j]=Math.min(255,Math.max(0,Math.round(255*light*(m.c.get(f[0])[j]+m.c.get(f[1])[j]+m.c.get(f[2])[j])/3)));paint.setColor(Color.rgb(col[0],col[1],col[2]));path.reset();path.moveTo(280+(a[0]-cx)*sc,280-(a[1]-cy)*sc);path.lineTo(280+(d[0]-cx)*sc,280-(d[1]-cy)*sc);path.lineTo(280+(e[0]-cx)*sc,280-(e[1]-cy)*sc);path.close();canvas.drawPath(path,paint);}
  return b;
 }
}
