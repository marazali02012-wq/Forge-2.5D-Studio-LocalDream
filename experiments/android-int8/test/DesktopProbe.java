package com.forgestudio.mobileprobe;
import java.io.*;import javax.imageio.ImageIO;import java.awt.*;import java.awt.image.*;import java.util.*;
public class DesktopProbe{
 public static void main(String[] args)throws Exception{
  File root=new File(args[0]),out=new File(args[1]);out.mkdirs();
  BufferedImage image=ImageIO.read(new File(root,"robot.png"));
  int w=image.getWidth(),h=image.getHeight(),x0=w,y0=h,x1=-1,y1=-1;boolean alpha=false;
  for(int y=0;y<h;y++)for(int x=0;x<w;x++){int a=image.getRGB(x,y)>>>24;if(a<255)alpha=true;if(a>0){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}}
  if(!alpha){x0=y0=0;x1=w-1;y1=h-1;}int sw=x1-x0+1,sh=y1-y0+1;double sc=512.0/Math.max(sw,sh)*(alpha?.85:1);int dw=(int)Math.round(sw*sc),dh=(int)Math.round(sh*sc);
  BufferedImage rgb=new BufferedImage(512,512,BufferedImage.TYPE_INT_RGB);Graphics2D g=rgb.createGraphics();g.setColor(new Color(128,128,128));g.fillRect(0,0,512,512);g.setRenderingHint(RenderingHints.KEY_INTERPOLATION,RenderingHints.VALUE_INTERPOLATION_BILINEAR);int dx=(512-dw)/2,dy=(512-dh)/2;g.drawImage(image,dx,dy,dx+dw,dy+dh,x0,y0,x1+1,y1+1,null);g.dispose();
  float[] input=new float[3*512*512];for(int y=0;y<512;y++)for(int x=0;x<512;x++){int i=y*512+x,p=rgb.getRGB(x,y);input[i]=((p>>16)&255)/255f;input[i+512*512]=((p>>8)&255)/255f;input[i+2*512*512]=(p&255)/255f;}
  Engine.Mesh m=Engine.run(new File(root,"models/triposr-encoder-int8.onnx"),new File(root,"models/triposr-decoder-fp32.onnx"),input,Float.parseFloat(args[2]),Float.parseFloat(args[3]),64,System.out::println);
  Engine.saveGlb(m,new File(out,"java-robot.glb"));
  try(PrintWriter p=new PrintWriter(new File(out,"java-report.json"))){p.printf(Locale.US,"{\"vertices\":%d,\"triangles\":%d,\"elapsed_ms\":%d,\"hwm_mib\":%d}%n",m.v.size(),m.f.size(),m.elapsedMs,m.hwmMiB);}
 }
}
