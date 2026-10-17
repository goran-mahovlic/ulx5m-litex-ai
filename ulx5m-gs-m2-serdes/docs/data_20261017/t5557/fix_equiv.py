import sys
src,dst=sys.argv[1:3]
s=open(src).read()
a=s.index("`ifdef HAVE_VENDOR_SERDES\n   wire link_ready")
b=s.index("`endif",a)+6
blk=s[a:b]; s=s[:a]+s[b:]
s=s.replace("   localparam  [7:0] MARK_K  = 8'hFF;\n","   localparam  [7:0] MARK_K  = 8'hFF;\n   wire link_ready;\n",1)
i=s.rindex("endmodule")
s=s[:i]+blk.replace("wire link_ready =","assign link_ready =")+"\n"+s[i:]
open(dst,"w").write(s)
