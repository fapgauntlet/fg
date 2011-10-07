import sys, os.path


if len(sys.argv) < 2:
    print 'This program will set the delay for all frames in a gif to the specified delay.'
    print 'Hit CTRL+C or type "exit" to exit.'
    gif_path = raw_input('enter a file path:\n')
    if gif_path[0] == '"' and gif_path[-1] == '"':
        gif_path = gif_path[1:-1]
    if gif_path == 'exit':
        exit()
    delay = raw_input('enter a (1/100ths of a second) delay to use for all frames:\n')
    if delay == 'exit':
        exit()
else:
    gif_path = sys.argv[1]
    delay = sys.argv[2]

if not os.path.isfile(gif_path):
    print 'invalid path:', gif_path

if not delay.isdigit():
    print 'delay must be an integer (whole number)'

delay = int(delay)

try:
    f = None
    f = open(gif_path, 'rb')
    f_read = f.read()
    f.close()
    bad_file = False
except:
    bad_file = True
finally:
    if f is not None:
        f.close()
if bad_file:
    print 'Could not open file:', gif_path
    if f is not None:
        f.close()
    exit()

header = f_read[:6]
if header not in ('GIF87a', 'GIF89a'):
    print 'Invalid gif file: header is not "GIF89a" or "GIF87a"'
    f.close()
    exit()

blocks = f_read.split('!')

# odds of failure are 1 in 4,294,967,296

cur = 0
for i, block in enumerate(blocks[:]):
    if len(block) >= 7:
        ext_label = block[0]
        blocksize = ord(block[1])
        if ext_label == '\xf9' and blocksize == 4:
            if len(block) == 7 or (len(block) >= 8 and block[7] == ','):
                print 'frame '+str(cur)+': '+str(ord(block[3])+ord(block[4])*256)+' -> '+str(delay)
                blocks[i] = block[:3] + chr(delay%256) + chr(delay/256) + block[5:]
                cur += 1

result = '!'.join(blocks)

try:
    dest_path = os.path.join(os.path.dirname(gif_path), 'setgifdelay_'+os.path.basename(gif_path))
    f = open(dest_path, 'wb')
    f.write(result)
    print 'successfully wrote file:',dest_path
except:
    print 'failed to create file:',dest_path
finally:
    f.close()
